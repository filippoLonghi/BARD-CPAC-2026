class Atmosphere {
  color bgColor, textColor, glowColor, particleColor;
  float particleSpeedY, particleCount, chaos;
  color nebulaColor;
  float nebulaAlphaMax, nebulaSpeed;

  Atmosphere(color bg, color txt, color gl, color pt,
             float spd, float cnt, float ch,
             color nebCol, float nebAlpha, float nebSpd) {
    bgColor       = bg; // background
    textColor     = txt;
    glowColor     = gl; // alone parole 
    particleColor = pt;
    particleSpeedY = spd;
    particleCount  = cnt; //numero particelle sfondo
    chaos          = ch; // 0-5
    nebulaColor    = nebCol;
    nebulaAlphaMax = nebAlpha; // opacità nebula 0-255
    nebulaSpeed    = nebSpd;
  }

  Atmosphere copy() {
    return new Atmosphere(bgColor, textColor, glowColor, particleColor,
                          particleSpeedY, particleCount, chaos,
                          nebulaColor, nebulaAlphaMax, nebulaSpeed);
  }
}
