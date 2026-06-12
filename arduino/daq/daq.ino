#include <LiquidCrystal.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 20, 4);

volatile int pulseCount = 0;

float flowRate = 0;
float oflowRate = 0;
float pressure = 0;
float totalVolume = 0;
float pulsesPerLiter = 175.0;

float P1_S = 0;
float P1_D = 0;
float P2_S = 0;
float P2_D = 0;

unsigned long lastTime = 0;

void pulseCounter() {
  pulseCount++;
}

int readADC(byte pin) {
  analogRead(pin);
  delayMicroseconds(20);
  return analogRead(pin);
}

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);  // HC-05
  lcd.init();
  lcd.backlight();

  pinMode(2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(2), pulseCounter, FALLING);
}

void loop() {

  if (millis() - lastTime >= 1000) {

    detachInterrupt(digitalPinToInterrupt(2));

    // Flow Rate
    float p = pulseCount;
    flowRate = (-0.00142 * p * p) + (5.892 * p) + 18.43;

    
    
    // Analog Pins for Pressure Sensors
    int rP1_S = readADC(A0);
    float vP1_S = rP1_S * (5.0 / 1023.0);
    P1_S = ((vP1_S - 0.5) * 30.0) / 4.0;
    
    int rP1_D = readADC(A1);
    float vP1_D = rP1_D * (5.0 / 1023.0);
    P1_D = ((vP1_D - 0.5) / 4.0) * 116.03;

    int rP2_S = readADC(A2);
    float vP2_S = rP2_S * (5.0 / 1023.0);
    P2_S = ((vP2_S - 0.5) * 30.0) / 4.0;
    
    int rP2_D = readADC(A3);
    float vP2_D = rP2_D * (5.0 / 1023.0);
    P2_D = ((vP2_D - 0.5) / 4.0) * 116.03;

    if (flowRate <= 18.43) flowRate = 0;
    if (pressure < 0) pressure = 0;
    
    if (P1_S < 0) P1_S = 0;
    if (P1_D < 0) P1_D = 0;
    if (P2_S < 0) P2_S = 0;
    if (P2_D < 0) P2_D = 0;

    // Timer (seconds)
    unsigned long timerSeconds = millis() / 1000;

    // COM3 Serial Monitor
    Serial.print(timerSeconds);
    Serial.print(", ");
    Serial.print(flowRate);
    Serial.print(", ");
    // Serial.println(pressure);
    
    Serial.print(P1_S); Serial.print(", ");
    Serial.print(P1_D); Serial.print(", ");
    Serial.print(P2_S); Serial.print(", ");
    Serial.println(P2_D);

    // COM4 Bluetooth 
    Serial1.print(timerSeconds);
    Serial1.print(",");
    Serial1.print(flowRate);
    Serial1.print(",");
    // Serial1.println(pressure);

    Serial1.print(P1_S); Serial1.print(",");
    Serial1.print(P1_D); Serial1.print(",");
    Serial1.print(P2_S); Serial1.print(",");
    Serial1.println(P2_D);

    // LCD Display
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Flow: ");
    lcd.print(flowRate, 4);
    lcd.print(" L/hr");

    lcd.setCursor(0, 1);
    // lcd.print("Press: ");
    // lcd.print(pressure, 4);
    // lcd.print(" psi");

    lcd.print(P1_S); lcd.print(",");
    lcd.print(P1_D); lcd.print(",");
    lcd.print(P2_S); lcd.print(",");
    lcd.print(P2_D);

    pulseCount = 0;

    attachInterrupt(digitalPinToInterrupt(2), pulseCounter, FALLING);

    lastTime = millis();
  }
}