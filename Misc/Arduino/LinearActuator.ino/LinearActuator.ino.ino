String Comm;
int linA = A0;             // Terminal A of linear Actuator (red wire) 
int linB = A1;             // Terminal B of linear Actuator (black wire)  
bool isData = false;
int i = 0;
bool A, B;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  pinMode(linA, OUTPUT);
  pinMode(linB, OUTPUT);
  digitalWrite(linA, LOW); // start in inserted position
  digitalWrite(linB, HIGH); //start in inserted position
  while(!Serial);  // wait for serial port to be opened
}

void flip() {
  
  A = digitalRead(linA);
  B = digitalRead(linB);
  digitalWrite(linA, !A);
  digitalWrite(linB, !B);
}

void loop() {
  // put your main code here, to run repeatedly:
  while(Serial.available() > 0){
    
    char value = Serial.read();
    Comm += value;
  
    if (value == '\n'){
      isData = true;
    }  
  }

  if (isData){
    isData = false;
    if(Comm.startsWith("EJECT")){
      Serial.print("Ejecting cartridge . . . ");
      Serial.print("\n");
      digitalWrite(linA, HIGH); 
      digitalWrite(linB, LOW);
    }
    else if (Comm.startsWith("INSERT")){
      Serial.print("Inserting cartridge . . . ");
      Serial.print("\n");
      digitalWrite(linA, LOW); 
      digitalWrite(linB, HIGH); 
    }
    else if (Comm.startsWith("INVERT")){
      Serial.print("Toggling linear actuator . . . ");
      Serial.print("\n");
      flip();
    }

    else {
      Serial.print("Unknown command.\n");
    }
    Comm = "";
  }
  delay(20);
}



