#include <Wire.h>
#include <I2Cdev.h>
// #include <MPU6050.h>
#include <MPU6050_9Axis_MotionApps41.h>

// Status LEDs.
#define GREEN_LED 7
#define RED_LED 8

bool toggle = true;

MPU6050 imu;

uint16_t imuPacketSize;
uint16_t imuFIFOCount;
uint8_t  imuFIFOBuffer[64];

Quaternion quaternion;  // [w, x, y, z]

volatile bool imuInt;
void imuIntFunc() {
  imuInt = true;
}

void readData() {
  imuInt = false;

  while (imuFIFOCount < imuPacketSize) imuFIFOCount = imu.getFIFOCount();
  imu.getFIFOBytes(imuFIFOBuffer, imuPacketSize);
  imuFIFOCount -= imuPacketSize;
}

void statusLight(bool state) {
  digitalWrite(GREEN_LED, state ? HIGH : LOW);
  digitalWrite(RED_LED, state ? LOW : HIGH);
}

void setup() {
  // Setup status LEDs.
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  statusLight(0);

  Wire.begin();

  Serial.begin(38400);

  imu.initialize();
  imu.dmpInitialize();
  imu.setDMPEnabled(true);
  attachInterrupt(0, imuIntFunc, RISING);
  imuPacketSize = imu.dmpGetFIFOPacketSize();

  statusLight(1);
}

void loop() {
  if (imuInt) {

    if (toggle = !toggle) {
      digitalWrite(GREEN_LED, HIGH);
    } else {
      digitalWrite(GREEN_LED, LOW);
    }

    if (imu.getIntStatus() & 0x02) {
      readData();
      imu.dmpGetQuaternion(&quaternion, imuFIFOBuffer);
      Serial.print(quaternion.w);
      Serial.print("\t");
      Serial.print(quaternion.x);
      Serial.print("\t");
      Serial.print(quaternion.y);
      Serial.print("\t");
      Serial.println(quaternion.z);
    }
  }
}
