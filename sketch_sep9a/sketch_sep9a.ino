#include <Wire.h>

// QMC5883P的I2C地址
const int QMC5883P_ADDR = 0x2C;

// 控制寄存器地址
const int MODE_REG = 0x0A;
const int CONFIG_REG = 0x0B;

// 数据输出寄存器地址
const int X_LSB_REG = 0x01;
const int X_MSB_REG = 0x02;
const int Y_LSB_REG = 0x03;
const int Y_MSB_REG = 0x04;
const int Z_LSB_REG = 0x05;
const int Z_MSB_REG = 0x06;

// 状态寄存器地址
const int STATUS_REG = 0x09;

// 初始化QMC5883P
void initQMC5883P() {
  Wire.begin();
  // 设置为连续测量模式，数据输出速率为200Hz，量程为±8G
  Wire.beginTransmission(QMC5883P_ADDR);
  Wire.write(MODE_REG);
  Wire.write(0xCF); // 0xCF: 连续模式, 200Hz数据输出速率
  Wire.endTransmission();

  Wire.beginTransmission(QMC5883P_ADDR);
  Wire.write(CONFIG_REG);
  Wire.write(0x08); // 0x08: 设置Set/Reset模式为开启，量程为±8G
  Wire.endTransmission();
}

// 读取QMC5883P的原始数据
void readQMC5883PData(int16_t& x, int16_t& y, int16_t& z) {
  Wire.beginTransmission(QMC5883P_ADDR);
  Wire.write(X_LSB_REG);
  Wire.endTransmission(false);
  Wire.requestFrom(QMC5883P_ADDR, 6);

  if (Wire.available() == 6) {
    byte x_lsb = Wire.read();
    byte x_msb = Wire.read();
    byte y_lsb = Wire.read();
    byte y_msb = Wire.read();
    byte z_lsb = Wire.read();
    byte z_msb = Wire.read();

    x = (x_msb << 8) | x_lsb;
    y = (y_msb << 8) | y_lsb;
    z = (z_msb << 8) | z_lsb;
  }
}

void setup() {
  Serial.begin(9600);
  initQMC5883P();
}

void loop() {
  int16_t x, y, z;
  readQMC5883PData(x, y, z);

  Serial.print("X: ");
  Serial.print(x);
  Serial.print("\tY: ");
  Serial.print(y);
  Serial.print("\tZ: ");
  Serial.println(z);

  delay(100);
}