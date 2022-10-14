#include "max6675.h"

int thermoDO = 4;
int thermoCS = 8;
int thermoCLK = 7;
String Command; // String command to rotate the holder
bool isData; 

MAX6675 thermocouple(thermoCLK, thermoCS, thermoDO);

void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("MAX6675 test");
  // wait for MAX chip to stabilize
  delay(500);
  Serial.println("Temperature probe ready");
}

void loop() {
  // basic readout test, just print the current temp

  while (Serial.available() > 0) {
    char value = Serial.read();
    Command += value;
    if (value == '\n') {
      isData = true;
    }
  }
  if (isData) {
    isData = false;

    if (Command.startsWith("readTemp")) {
      readTemperature();
    }
  Command = "";
  }


delay(20);
}



void readTemperature(){
  
  Serial.print(thermocouple.readCelsius());
  Serial.print(" deg C\n");
  Serial.println("");
  Serial.print("ACK\n");
  }
