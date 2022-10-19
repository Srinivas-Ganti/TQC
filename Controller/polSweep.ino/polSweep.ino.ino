#include "Adafruit_MAX31855.h"

#define thermoDO 4
#define thermoCS 8
#define thermoCLK 7
#define STEPPER_PIN_1 9
#define STEPPER_PIN_2 10
#define STEPPER_PIN_3 11
#define STEPPER_PIN_4 12
#define limSwitch 6

double temperature;
double errorCompensation = -24.5;

Adafruit_MAX31855 thermocouple(thermoCLK, thermoCS, thermoDO);

bool isData; 
bool dir;
bool homed = false; //initially assume the motor is not homed
const double offset = 114; //angle offset to align cartridge back from home limit.
String Command;
float angle; // angle requested by user
double pos;  //current position
double target; // variable requested angle
double toGo; // difference between pos and target
int i = 0; // step instruction 
int step_number = 0;
const int homingDelay = 4000;
const int movementDelay = 2000;
const int stepsPerDegree = 28;  


void setup() {
pinMode(thermoCLK, OUTPUT);
pinMode(thermoCS, OUTPUT);
pinMode(thermoDO, INPUT);
pinMode(STEPPER_PIN_1, OUTPUT);
pinMode(STEPPER_PIN_2, OUTPUT);
pinMode(STEPPER_PIN_3, OUTPUT);
pinMode(STEPPER_PIN_4, OUTPUT);
pinMode(limSwitch, INPUT);

Serial.begin(115200);
while (!Serial);
digitalWrite(thermoCS, LOW);
delay(500);
Serial.println("MAX31855 probe ready");
Serial.println("Polarisation sweep controller: READY");
Serial.print("Enter rotation in degrees: rot+45, rot-45");
}


void loop() {
  while (Serial.available() > 0){
    char value = Serial.read();
    Command += value;
    if(value == '\n'){
      isData = true;
      }
    }
    if(isData){
      isData = false;
      
      if (Command.startsWith("home")){
        home();
        }
      else if(Command.startsWith("rot")){
        rotate(Command);
        }
      else if (Command.startsWith("readTemp")) {
      readTemperature();
       } 
       
      else if(Command.startsWith("pos")){
        position();
        }    
   Command = "";
  }
  delay(20); 
  
}

void readTemperature(){
  temperature = thermocouple.readCelsius() + errorCompensation;
  Serial.print(temperature);
  Serial.print(" deg C\n");
  Serial.println("");
  Serial.print("ACK\n");
  }


void home(){
  Serial.print("Homing cartridge . . . ");
  for (int i = 0; i < 300000 && !digitalRead(limSwitch); i++) {
    OneStep(false);
    Serial.println(digitalRead(limSwitch));
    delayMicroseconds(homingDelay);
  }
  for (int i = 0; i < 300000 && digitalRead(limSwitch); i++) {
    OneStep(true);
    Serial.println(digitalRead(limSwitch));
    delayMicroseconds(homingDelay);
  }
  homed = true;
  //Serial.println("Applying offset . . .");
  rotate("rot+" + String(offset));
  pos = 0;                   // HOME CARTRIDGES
  //Serial.println("Cartridges homed");
  Serial.println("");
  Serial.print("ACK\n");
}


void position(){
  Serial.println("Current position: ");
  Serial.println(pos);
  }



void rotate(String str) {
  if (!homed){
    home();
  }
  Serial.println("Rotating by: ");
  Serial.println(str);
  angle = str.substring(4).toDouble();
  
  if (str[3] == '+'){
    dir = true;
    Serial.println("Rotation direction: (+)  ccw");
    pos += angle;
    }
  else if (str[3] == '-'){
    dir = false;
    Serial.println("Roation direction: (-) cw");
    pos -= angle;
    }
  
  Serial.println("Angle requested:");
  Serial.println(angle);
  
  for(int j = 0; j<=int(angle*stepsPerDegree); j++){
    OneStep(dir);
    delayMicroseconds(movementDelay);
    }
  
  Serial.println("Current angle: "+String(pos));  
  Serial.println("");
  Serial.print("ACK\n");
  }


void OneStep(bool dir){
    if(dir){
switch(step_number){
  case 0:
  digitalWrite(STEPPER_PIN_1, HIGH);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, LOW);
  break;
  case 1:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, HIGH);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, LOW);
  break;
  case 2:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, HIGH);
  digitalWrite(STEPPER_PIN_4, LOW);
  break;
  case 3:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, HIGH);
  break;
} 
  }else{
    switch(step_number){
  case 0:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, HIGH);
  break;
  case 1:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, HIGH);
  digitalWrite(STEPPER_PIN_4, LOW);
  break;
  case 2:
  digitalWrite(STEPPER_PIN_1, LOW);
  digitalWrite(STEPPER_PIN_2, HIGH);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, LOW);
  break;
  case 3:
  digitalWrite(STEPPER_PIN_1, HIGH);
  digitalWrite(STEPPER_PIN_2, LOW);
  digitalWrite(STEPPER_PIN_3, LOW);
  digitalWrite(STEPPER_PIN_4, LOW);  
} 
  }
step_number++;
  if(step_number > 3){
    step_number = 0;
  }
}
