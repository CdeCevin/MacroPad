#include <Keypad.h>

const byte numRows = 4; //number of rows on the keypad
const byte numCols = 4; //number of columns on the keypad

//keymap defines the key pressed according to the row and columns just as appears on the keypad
char keymap[numRows][numCols]= 
{
  {'4', '8', '#', 'D'}, 
  {'3', '7', '*', 'C'}, 
  {'2', '6', '0', 'B'},
  {'1', '5', '9', 'A'}
};

//Code that shows the the keypad connections to the arduino terminals
byte colPins[numRows] = {5,4,3,2}; //Rows 0 to 3
byte rowPins[numCols]= {8,9,10,11};  //Columns 0 to 3

//initializes an instance of the Keypad class
Keypad myKeypad= Keypad(makeKeymap(keymap), rowPins, colPins, numRows, numCols);

void setup()
{
  Serial.begin(9600);
}

void loop()
{
  char keypressed = myKeypad.getKey();

  // Imprimir la tecla presionada
  if (keypressed != NO_KEY)
  {
    Serial.println(keypressed);
  }
}
