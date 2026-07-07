class FlyingWord { 
  // oggetto per ogni parola singola mandata da SentenceDisplay
  String text;
  PVector target, pos, startPos, vel, acc;
  int sentenceId; // forse non lo sto più usando
  boolean active = false;
  boolean locked = false;
  float currentGlow = 0;
  float targetGlow  = 0;
  float colorVariation; //varia un pochino il colore di ciascuna parola randomly
  float flightSpeed  = 8.8;
  float opacity = 255;
  int flightStartMs = 0;
  int flightEndMs = 1;


  FlyingWord(String text, float targetX, float targetY, int sentenceId) {
    this.text           = text;
    this.target         = new PVector(targetX, targetY);
    this.sentenceId     = sentenceId;
    this.colorVariation = random(0.0f, 0.4f); 

    // parte da un bordo casuale, ma preferibilmente dal basso
    // (le parole "salgono" verso la zona testo che è in basso)
    int side = floor(random(4));
    float dist = 280;
    if (side == 0) pos = new PVector(random(width), -dist);
    else if (side == 1) pos = new PVector(width + dist, random(height));
    else if (side == 2) pos = new PVector(random(width), height + dist);
    else               pos = new PVector(-dist, random(height));
    startPos = pos.copy();

    vel = new PVector(0, 0);
    acc = new PVector(0, 0);
  }

  void scheduleFlight(int startMs, int endMs) {
    flightStartMs = max(0, startMs);
    flightEndMs = max(flightStartMs + 1, endMs);
  }


  void update(int elapsedMs) {
  currentGlow = lerp(currentGlow, targetGlow, 0.1f);
  if (elapsedMs < flightStartMs) {
    active = false;
    return;
  }
  active = true;

  if (locked) return;

  PVector desired = PVector.sub(target, pos);
  float distance = desired.mag();

  float maxSpeed = 12.0f;     
  float maxForce = 0.7f;      
  float brakingRadius = 130.0f; 

  if (distance < brakingRadius) {
    float m = map(distance, 0, brakingRadius, 0, maxSpeed);
    desired.setMag(m);
  } else {
    desired.setMag(maxSpeed);
  }

  PVector steer = PVector.sub(desired, vel);
  steer.limit(maxForce); 

  acc.add(steer);
  vel.add(acc);
  pos.add(vel);
  acc.mult(0); 

  if (distance < 1.0f && vel.mag() < 0.1f) {
    lockToTarget();
  }
}

  void lockToTarget() {
    pos = target.copy();
    vel.mult(0);
    acc.mult(0);
    //angle = 0;
    locked = true;
  }

  void displayBase(color cBase, color cAccent) {
    textFont(myFont, fontSize);
    pushMatrix();
    translate(pos.x, pos.y);
    //rotate(angle); ///???
    color finalColor = lerpColor(cBase, cAccent, colorVariation);
    fill(red(finalColor), green(finalColor), blue(finalColor), opacity);
    fill(0, min(150, opacity * 0.55f));
    text(text, 2, 2);
    fill(red(finalColor), green(finalColor), blue(finalColor), opacity);
    text(text, 0, 0);
    popMatrix();
  }

  void displayGlowingOnly(color cGlow) {
    textFont(myFont, fontSize);
    textSize(fontSize);
    pushMatrix();
    translate(pos.x, pos.y);
    float intensity = currentGlow / 255.0f;
    float pulse     = 1.0f + 0.15f * sin(millis() / 250.0f);
    fill(red(cGlow), green(cGlow), blue(cGlow), 40.0f * intensity * pulse);
    for (int i = -2; i <= 2; i += 2) {
      text(text, i, 0);
      text(text, 0, i);
    }
    fill(red(cGlow), green(cGlow), blue(cGlow), 100.0f * intensity);
    text(text, 0, 0);
    fill(255, 255, 255, 150.0f * intensity);
    text(text, 0, 0);
    popMatrix();
  }
}
