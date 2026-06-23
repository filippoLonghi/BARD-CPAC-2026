class MoodManager {
  
  HashMap<String, Atmosphere> moods;
  Atmosphere startMood, targetMood, currentVals;
  float transitionDuration  = 2200; // durata transizione atmosfera in ms
  float transitionStartTime = -9999; // timestamp inizio transizione
 

  MoodManager(String initialMood){
    setupMoods();
    setMood(initialMood);
    currentVals = targetMood.copy();
    startMood = targetMood.copy();
  }
  
  
  void setMood(String name) {
    String normalized = name == null ? "CALM" : name.trim().toUpperCase();
    if (moods.containsKey(normalized)) {
      if (currentVals != null) startMood = currentVals.copy();
      targetMood = moods.get(normalized);
      transitionStartTime = millis();
    } else {
      println(">>> Unknown mood, using CALM: " + name);
      setMood("CALM");
    }
  }
  
  void setupMoods() {
    moods = new HashMap<String, Atmosphere>(); 
    /*moods.put("ENERGETIC", new Atmosphere(color(40, 10, 5), color(240, 220, 180), color(255, 160, 20), color(255, 100, 50), -3.0f, 250.0f, 5.0f, color(255, 80, 20), 200.0f, 0.03f));
    moods.put("SOLO", new Atmosphere(color(15, 15, 18), color(210, 210, 215), color(180, 180, 200), color(0, 0, 0, 0), 0f, 0f, 0f, color(50, 50, 60), 60.0f, 0.002f));
    moods.put("CALM", new Atmosphere(color(20, 15, 35), color(170, 180, 210), color(100, 150, 255), color(150, 100, 200), -0.3f, 60.0f, 0.2f, color(80, 100, 220), 150.0f, 0.008f));
    moods.put("DEEP", new Atmosphere(color(2, 5, 15), color(110, 130, 150), color(0, 100, 200), color(0, 50, 100), 0.1f, 100.0f, 0.5f, color(0, 40, 120), 180.0f, 0.005f));
    moods.put("DISSONANT", new Atmosphere(color(15, 20, 18), color(190, 210, 190), color(50, 255, 50), color(100, 255, 100), 1.0f, 150.0f, 2.0f, color(40, 200, 40), 160.0f, 0.015f));
    moods.put("ANXIOUS", new Atmosphere(color(30, 5, 0), color(220, 150, 150), color(255, 20, 20), color(150, 50, 0), 4.0f, 300.0f, 1.5f, color(200, 20, 20), 220.0f, 0.025f));
  */
    moods.put("DARK", new Atmosphere(color(11, 2, 17), color(170, 180, 200), color(50, 80, 150), color(30, 40, 80), 0.3f, 80.0f, 0.2f, color(20, 40, 80), 150.0f, 0.004f));
    moods.put("CALM", new Atmosphere(color(30, 20, 75), color(240, 240, 255), color(150, 100, 255), color(100, 80, 180), -0.3f, 60.0f, 0.1f, color(120, 80, 200), 150.0f, 0.008f));
    moods.put("ANXIOUS", new Atmosphere(color(85, 60, 150), color(255, 255, 200), color(200, 50, 255), color(150, 100, 255), 4.0f, 300.0f, 0.8f, color(180, 40, 180), 220.0f, 0.025f));
    moods.put("DENSE", new Atmosphere(color(45, 45, 65), color(210, 210, 220), color(100, 120, 180), color(80, 80, 100), 0.1f, 120.0f, 0.4f, color(70, 90, 130), 180.0f, 0.005f));
    moods.put("RISING TENSION", new Atmosphere(color(120, 60, 85), color(250, 200, 210), color(200, 50, 100), color(180, 80, 100), -3.0f, 250.0f, 1.0f, color(150, 40, 70), 200.0f, 0.03f));
    moods.put("RELEASE", new Atmosphere(color(210, 140, 130), color(255, 255, 255), color(255, 230, 200), color(255, 255, 210), 0.8f, 150.0f, 0.2f, color(11, 2, 17), 180.0f, 0.008f));
    moods.put("BRIGHT", new Atmosphere(color(180, 140, 40), color(255, 255, 240), color(255, 255, 180), color(255, 255, 255), -2.0f, 200.0f, 0.8f, color(250, 250, 150), 180.0f, 0.02f));
    moods.put("SPARSE", new Atmosphere(color(190, 130, 150), color(60, 20, 40), color(230, 180, 200), color(255, 255, 255), 0f, 60.0f, 0.1f, color(160, 100, 120), 60.0f, 0.002f));
  }
  
  void updateCurrentAtmosphere(float smoothT) {
    currentVals.bgColor        = lerpColor(startMood.bgColor,        targetMood.bgColor,        smoothT);
    currentVals.textColor      = lerpColor(startMood.textColor,      targetMood.textColor,      smoothT);
    currentVals.glowColor      = lerpColor(startMood.glowColor,      targetMood.glowColor,      smoothT);
    currentVals.particleColor  = lerpColor(startMood.particleColor,  targetMood.particleColor,  smoothT);
    currentVals.particleSpeedY = lerp(startMood.particleSpeedY, targetMood.particleSpeedY, smoothT);
    currentVals.chaos          = lerp(startMood.chaos,           targetMood.chaos,           smoothT);
    currentVals.nebulaColor    = lerpColor(startMood.nebulaColor,    targetMood.nebulaColor,    smoothT);
    currentVals.nebulaAlphaMax = lerp(startMood.nebulaAlphaMax,  targetMood.nebulaAlphaMax,  smoothT);
    currentVals.nebulaSpeed    = lerp(startMood.nebulaSpeed,     targetMood.nebulaSpeed,     smoothT);
    currentVals.particleCount  = lerp(startMood.particleCount,   targetMood.particleCount,   smoothT);
  }

  Atmosphere getCurrentVals(){
    return this.currentVals;
  }
  
  void update() {
    float elapsed = millis() - transitionStartTime;
    float t       = constrain(elapsed / transitionDuration, 0, 1);
    float smoothT = t * t * (3 - 2 * t);
    updateCurrentAtmosphere(smoothT);
  }
}
