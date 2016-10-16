#include <stdio.h>
#include <avrm/uart.h>
#include <util/delay.h>

int main(void)
{
  uart_init();
  for (;;) {
    printf("Hello World!\n");
    _delay_ms(1000);
  }
  return 0;
}
