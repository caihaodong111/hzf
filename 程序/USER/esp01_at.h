#ifndef __ESP01_AT_H
#define __ESP01_AT_H

#include "stm32f10x.h"

#define ESP01_UART_BAUD           9600U
#define ESP01_UART_BAUD_FALLBACK  115200U

#define ESP01_WIFI_SSID      "ChinaNet-DpMd"
#define ESP01_WIFI_PASSWORD  "s78xcenq"

#define ESP01_HTTP_HOST      "192.168.1.3"
#define ESP01_HTTP_PORT      8080U
#define ESP01_HTTP_PATH      "/sensor"

uint8_t ESP01_BasicSetup(void);
uint8_t ESP01_ConnectWiFi(void);
uint8_t ESP01_ReportSensorsHttpGet(float ph, float turbidity, float temperature, float tds);

#endif
