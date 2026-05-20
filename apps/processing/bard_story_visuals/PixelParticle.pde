class PixelParticle {
  PVector pos, target;
  color currentColor, targetColor;
  float size;
  float noiseOffset;

  PixelParticle(float tx, float ty, color tc) {
    // Nascono in una posizione casuale vicino al target
    pos = new PVector(tx + random(-3, 3), ty + random(-3, 3));
    target = new PVector(tx, ty);
    currentColor = tc;
    targetColor = tc;
    size = random(1.5, 3.5);
    noiseOffset = random(1000);
  }
  
  void setNewTarget(float tx, float ty, color tc) {
    target.x = tx;
    target.y = ty;
    targetColor = tc;
  }

  void update(float chaos) {
    // Lerp verso il target: crea l'effetto "composizione"
    pos.x = lerp(pos.x, target.x, 0.05); // 5% per frame velocità verso la nuova posizione di quel pixel
    pos.y = lerp(pos.y, target.y, 0.05);
    currentColor = lerpColor(currentColor, targetColor, 0.04); // 4% per frame velocità verso il nuovo colore
    
    chaos *=0.3;
    // noise per farle vibrare
    pos.x += map(noise(noiseOffset + millis()*0.001), 0, 1, -chaos, chaos);
    pos.y += map(noise(noiseOffset + 1000 + millis()*0.001), 0, 1, -chaos, chaos);
  }

  void display(float globalAlpha) { //stiamo usando alpha solo a 255
    noStroke();
    fill(currentColor, globalAlpha);
    ellipse(pos.x, pos.y, size, size);
  }
}
