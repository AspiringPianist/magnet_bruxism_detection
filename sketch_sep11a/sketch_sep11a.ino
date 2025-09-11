#include <Wire.h>

#define MPU6050_ADDR 0x68
#define INT_PIN_CFG 0x37
#define MAG_ADDR 0x0D  // Magnetometer I2C address

void setup() {
  Wire.begin();
  Serial.begin(9600);
  while (!Serial);

  Serial.println("Starting MPU6050 bypass & Magnetometer read demo...");

  // Enable MPU6050 bypass mode to access magnetometer directly
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(INT_PIN_CFG);     // INT_PIN_CFG register
  Wire.write(0x02);            // Enable BYPASS_EN bit
  Wire.endTransmission();

  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x6A);            // USER_CTRL register
  Wire.write(0x00);            // Disable master mode, allow bypass
  Wire.endTransmission();

  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x6B);            // PWR_MGMT_1 register
  Wire.write(0x00);            // Clear sleep bit, wake up device
  Wire.endTransmission();

  delay(100);

  // Initialize magnetometer (QMC5883L/HA5883)
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(0x09);            // Control register 1
  Wire.write(0x1D);            // Continuous measurement mode, 10Hz, 2G range
  Wire.endTransmission();

  delay(100);

  Serial.println("Initialization complete. Reading magnetometer...");
}

void loop() {
  int16_t x, y, z;

  // Request 6 bytes of data starting from register 0x00
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(0x00);
  Wire.endTransmission();
  Wire.requestFrom(MAG_ADDR, 6);

  if (Wire.available() == 6) {
    uint8_t xL = Wire.read();
    uint8_t xH = Wire.read();
    uint8_t yL = Wire.read();
    uint8_t yH = Wire.read();
    uint8_t zL = Wire.read();
    uint8_t zH = Wire.read();

    x = (int16_t)(xH << 8 | xL);
    y = (int16_t)(yH << 8 | yL);
    z = (int16_t)(zH << 8 | zL);

    Serial.print("Magnetometer X: ");
    Serial.print(x);
    Serial.print(" Y: ");
    Serial.print(y);
    Serial.print(" Z: ");
    Serial.println(z);
  } else {
    Serial.println("Failed to read magnetometer data");
  }

  delay(200);
}
