#include "main.h"
#include "esp01_at.h"
#include "debug_uart.h"

#define DEBUG_UART_BAUD   115200U
#define SENSOR_SCAN_MS    1000U
#define ESP_RETRY_MS      5000U
#define UPLOAD_PERIOD_MS  15000U
#define HEARTBEAT_MS      500U
#define LOOP_DELAY_MS     20U

u8 b_1s = 0;
u8 eer_f = 0;
u8 smart_config = 0;
u8 run_mod = 0;
u8 mod = 0;

u32 set_code[21] = {0};

float PH = 0.0f;
float PH_temp = 0.0f;
float PH_voltage = 0.0f;
u16 temperature = 0;
float temperature_temp = 0.0f;
float turbidity = 0.0f;
float turbidity_temp = 0.0f;
float TDS_DAT = 0.0f;

static uint32_t clamp_u32(float value)
{
    if (value <= 0.0f)
    {
        return 0U;
    }

    return (uint32_t)(value + 0.5f);
}

static long scale_x10(float value)
{
    if (value >= 0.0f)
    {
        return (long)(value * 10.0f + 0.5f);
    }

    return (long)(value * 10.0f - 0.5f);
}

static void Sensors_Init(void)
{
    ADC1_DMA_Config();

    if (DS18B20_Init() != 0)
    {
        DebugUart_SendString("DS18B20 not found on PB1\r\n");
    }
    else
    {
        DebugUart_SendString("DS18B20 ready on PB1\r\n");
    }
}

static void Heartbeat_Init(void)
{
    GPIO_InitTypeDef gpio_init;

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOC, ENABLE);

    gpio_init.GPIO_Pin = GPIO_Pin_13;
    gpio_init.GPIO_Speed = GPIO_Speed_2MHz;
    gpio_init.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(GPIOC, &gpio_init);

    GPIO_SetBits(GPIOC, GPIO_Pin_13);
}

static void Heartbeat_Toggle(void)
{
    if (GPIO_ReadOutputDataBit(GPIOC, GPIO_Pin_13) == Bit_SET)
    {
        GPIO_ResetBits(GPIOC, GPIO_Pin_13);
    }
    else
    {
        GPIO_SetBits(GPIOC, GPIO_Pin_13);
    }
}

static void Sensors_Update(void)
{
    float tds_voltage;

    PH_voltage = ((float)ADCConvertedValue[1] * 3.3f) / 4095.0f;
    PH = PH_voltage * (-5.7541f) + 16.654f;
    if (PH > 14.0f)
    {
        PH = 14.0f;
    }
    if (PH < 0.0f)
    {
        PH = 0.0f;
    }
    PH_temp = PH;

    turbidity = ((float)ADCConvertedValue[0] * 3.3f) / 4096.0f;
    turbidity = 2047.19f - turbidity * 865.68f;
    turbidity = turbidity - 200.0f;
    if (turbidity < 35.0f)
    {
        turbidity = 0.0f;
    }
    turbidity_temp = turbidity;

    tds_voltage = ((float)ADCConvertedValue[2] / 4095.0f) * 3.3f;
    TDS_DAT = 66.71f * tds_voltage * tds_voltage * tds_voltage
            - 127.93f * tds_voltage * tds_voltage
            + 428.7f * tds_voltage;
    if (TDS_DAT < 20.0f)
    {
        TDS_DAT = 0.0f;
    }

    temperature = (u16)DS18B20_Get_Temp();
    temperature_temp = (float)temperature / 10.0f;
}

static void Debug_PrintSensors(void)
{
    char log_line[128];
    long ph_x10 = scale_x10(PH_temp);
    long ph_v_x1000 = scale_x10(PH_voltage * 100.0f);
    long temp_x10 = scale_x10(temperature_temp);

    snprintf(
        log_line,
        sizeof(log_line),
        "ADC[%u,%u,%u] PH_ADC=%u PH_V=%ld.%03ld PH=%ld.%01ld TDS=%lu Turb=%lu Temp=%ld.%01ld\r\n",
        (unsigned int)ADCConvertedValue[0],
        (unsigned int)ADCConvertedValue[1],
        (unsigned int)ADCConvertedValue[2],
        (unsigned int)ADCConvertedValue[1],
        ph_v_x1000 / 1000,
        ph_v_x1000 >= 0 ? (ph_v_x1000 % 1000) : -(ph_v_x1000 % 1000),
        ph_x10 / 10,
        ph_x10 >= 0 ? (ph_x10 % 10) : -(ph_x10 % 10),
        (unsigned long)clamp_u32(TDS_DAT),
        (unsigned long)clamp_u32(turbidity_temp),
        temp_x10 / 10,
        temp_x10 >= 0 ? (temp_x10 % 10) : -(temp_x10 % 10)
    );
    DebugUart_SendString(log_line);
}

int main(void)
{
    uint32_t app_ms = 0U;
    uint32_t last_sensor_ms = 0U;
    uint32_t last_retry_ms = 0U;
    uint32_t last_upload_ms = 0U;
    uint32_t last_heartbeat_ms = 0U;
    uint8_t esp_ready = 0U;
    uint8_t wifi_ready = 0U;

    DelayInit();
    DelayMs(200);

    Heartbeat_Init();
    DebugUart_Init(DEBUG_UART_BAUD);
    DebugUart_SendString("\r\nAT sensor node boot\r\n");
    Sensors_Init();
    usart2_init(ESP01_UART_BAUD);

    while (1)
    {
        if ((app_ms - last_heartbeat_ms) >= HEARTBEAT_MS)
        {
            last_heartbeat_ms = app_ms;
            Heartbeat_Toggle();
        }

        if ((app_ms - last_sensor_ms) >= SENSOR_SCAN_MS)
        {
            last_sensor_ms = app_ms;
            Sensors_Update();
            Debug_PrintSensors();
        }

        if ((app_ms - last_retry_ms) >= ESP_RETRY_MS)
        {
            last_retry_ms = app_ms;

            if (esp_ready == 0U)
            {
                esp_ready = ESP01_BasicSetup();
                if (esp_ready == 0U)
                {
                    wifi_ready = 0U;
                }
            }
            else if (wifi_ready == 0U)
            {
                wifi_ready = ESP01_ConnectWiFi();
            }
        }

        if ((esp_ready != 0U) &&
            (wifi_ready != 0U) &&
            ((app_ms - last_upload_ms) >= UPLOAD_PERIOD_MS))
        {
            last_upload_ms = app_ms;
            if (ESP01_ReportSensorsHttpGet(PH_temp, turbidity_temp, temperature_temp, TDS_DAT) == 0U)
            {
                wifi_ready = 0U;
            }
        }

        DelayMs(LOOP_DELAY_MS);
        app_ms += LOOP_DELAY_MS;
    }
}
