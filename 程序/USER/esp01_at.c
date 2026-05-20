#include "main.h"
#include "esp01_at.h"
#include "debug_uart.h"

#include <stdio.h>
#include <stdarg.h>
#include <string.h>

static void ESP01_DebugLogf(const char *fmt, ...)
{
    char log_line[96];
    va_list args;

    va_start(args, fmt);
    vsnprintf(log_line, sizeof(log_line), fmt, args);
    va_end(args);

    DebugUart_SendString(log_line);
}

static void ESP01_LogRawReply(void)
{
    const char *rx = USART2_GetRxBuffer();

    if ((rx != NULL) && (rx[0] != '\0'))
    {
        DebugUart_SendString("ESP01 raw reply: ");
        DebugUart_SendString(rx);
        DebugUart_SendString("\r\n");
    }
}

static uint8_t ESP01_ConfigMissing(const char *value)
{
    return (strncmp(value, "YOUR_", 5) == 0);
}

static long ESP01_ScaleX10(float value)
{
    if (value >= 0.0f)
    {
        return (long)(value * 10.0f + 0.5f);
    }

    return (long)(value * 10.0f - 0.5f);
}

static uint32_t ESP01_ClampU32(float value)
{
    if (value <= 0.0f)
    {
        return 0U;
    }

    return (uint32_t)(value + 0.5f);
}

static uint8_t ESP01_WaitReply(const char *expect, uint32_t timeout_ms)
{
    while (timeout_ms > 0U)
    {
        const char *rx = USART2_GetRxBuffer();

        if ((expect != NULL) && (strstr(rx, expect) != NULL))
        {
            return 1U;
        }

        if ((strstr(rx, "ERROR") != NULL) ||
            (strstr(rx, "FAIL") != NULL) ||
            (strstr(rx, "busy") != NULL))
        {
            return 0U;
        }

        DelayMs(1);
        timeout_ms--;
    }

    return 0U;
}

static uint8_t ESP01_SendCommand(const char *cmd, const char *expect, uint32_t timeout_ms)
{
    USART2_ClearRxBuffer();
    u2_printf("%s\r\n", cmd);
    return ESP01_WaitReply(expect, timeout_ms);
}

uint8_t ESP01_BasicSetup(void)
{
    static const uint32_t baud_candidates[] = {
        ESP01_UART_BAUD,
        ESP01_UART_BAUD_FALLBACK
    };
    uint32_t i;

    for (i = 0U; i < (sizeof(baud_candidates) / sizeof(baud_candidates[0])); i++)
    {
        if ((i > 0U) && (baud_candidates[i] == baud_candidates[0]))
        {
            continue;
        }

        usart2_init(baud_candidates[i]);
        ESP01_DebugLogf("ESP01 try baud %lu\r\n", (unsigned long)baud_candidates[i]);

        if (ESP01_SendCommand("AT", "OK", 1000U))
        {
            ESP01_SendCommand("ATE0", "OK", 1000U);
            ESP01_SendCommand("AT+CWMODE=1", "OK", 1000U);
            ESP01_SendCommand("AT+CIPMUX=0", "OK", 1000U);
            ESP01_SendCommand("AT+CWAUTOCONN=1", "OK", 1000U);

            ESP01_DebugLogf("ESP01 AT ready at %lu\r\n", (unsigned long)baud_candidates[i]);
            return 1U;
        }

        ESP01_LogRawReply();
    }

    DebugUart_SendString("ESP01 no AT response. Check baud, EN and wiring.\r\n");
    return 0U;
}

uint8_t ESP01_ConnectWiFi(void)
{
    char cmd[160];

    if (ESP01_ConfigMissing(ESP01_WIFI_SSID) || ESP01_ConfigMissing(ESP01_WIFI_PASSWORD))
    {
        DebugUart_SendString("Set ESP01_WIFI_SSID and ESP01_WIFI_PASSWORD first\r\n");
        return 0U;
    }

    snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"", ESP01_WIFI_SSID, ESP01_WIFI_PASSWORD);
    if (!ESP01_SendCommand(cmd, "OK", 20000U))
    {
        DebugUart_SendString("ESP01 WiFi connect failed\r\n");
        return 0U;
    }

    DebugUart_SendString("ESP01 WiFi connected\r\n");
    return 1U;
}

uint8_t ESP01_ReportSensorsHttpGet(float ph, float turbidity, float temperature, float tds)
{
    char cmd[96];
    char request[256];
    long ph_x10 = ESP01_ScaleX10(ph);
    long temp_x10 = ESP01_ScaleX10(temperature);
    uint32_t tds_u32 = ESP01_ClampU32(tds);
    uint32_t turb_u32 = ESP01_ClampU32(turbidity);
    uint16_t request_len;

    if (ESP01_ConfigMissing(ESP01_HTTP_HOST))
    {
        DebugUart_SendString("Set ESP01_HTTP_HOST before upload\r\n");
        return 0U;
    }

    ESP01_SendCommand("AT+CIPCLOSE", "OK", 500U);

    snprintf(
        cmd,
        sizeof(cmd),
        "AT+CIPSTART=\"TCP\",\"%s\",%u",
        ESP01_HTTP_HOST,
        (unsigned int)ESP01_HTTP_PORT
    );
    if (!ESP01_SendCommand(cmd, "OK", 8000U))
    {
        DebugUart_SendString("ESP01 TCP connect failed\r\n");
        return 0U;
    }

    snprintf(
        request,
        sizeof(request),
        "GET %s?ph=%ld.%01ld&tds=%lu&turb=%lu&temp=%ld.%01ld HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Connection: close\r\n"
        "\r\n",
        ESP01_HTTP_PATH,
        ph_x10 / 10,
        ph_x10 >= 0 ? (ph_x10 % 10) : -(ph_x10 % 10),
        (unsigned long)tds_u32,
        (unsigned long)turb_u32,
        temp_x10 / 10,
        temp_x10 >= 0 ? (temp_x10 % 10) : -(temp_x10 % 10),
        ESP01_HTTP_HOST
    );

    request_len = (uint16_t)strlen(request);
    snprintf(cmd, sizeof(cmd), "AT+CIPSEND=%u", (unsigned int)request_len);
    if (!ESP01_SendCommand(cmd, ">", 5000U))
    {
        DebugUart_SendString("ESP01 CIPSEND failed\r\n");
        return 0U;
    }

    USART2_ClearRxBuffer();
    USART2_SendBuffer((const uint8_t *)request, request_len);
    if (!ESP01_WaitReply("SEND OK", 8000U))
    {
        DebugUart_SendString("ESP01 SEND failed\r\n");
        return 0U;
    }

    ESP01_SendCommand("AT+CIPCLOSE", "OK", 2000U);
    DebugUart_SendString("ESP01 upload ok\r\n");
    return 1U;
}
