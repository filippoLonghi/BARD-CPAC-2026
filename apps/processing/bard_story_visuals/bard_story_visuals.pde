import java.util.HashMap;
import oscP5.*;
import netP5.*;

//  RETE 
OscP5 oscP5;
String ip = "127.0.0.1";
int port = 5005;
NetAddress pythonVoiceLocation;

//  LISTA ORDINATA SEGMENTI TESTUALI
ArrayList<Segmento> playlist = new ArrayList<Segmento>(); 

//  TIMING 
float slideDuration = 10.0;
boolean isPlaying = false;
int currentSegmentIndex = -1;
int lastSegmentTime = 0;

//  LAYOUT 
float imageAreaRatio = 0.55; // quanto schermo (in altezza) occupa l'area immagine
float imageMarginX   = 0.2; // margine laterale dell'immagine in %
float imageMarginTop = 0.13;
float textAreaPad    = 32; // padding in pixel tra il bordo inferiore dell'immagine e il testo

//  FONT & TESTO 
int   fontSize = 20;
float leading  = fontSize * 1.45; // interlinea
PFont myFont;
String fullText = "";

// SISTEMA GESTIONE PAROLE 
WordsSystem wordsystem = new WordsSystem();

//  PARTICELLE SFONDO
ArrayList<BgParticle> bgParticles = new ArrayList<BgParticle>();

//  ATMOSFERA 
MoodManager moodManager;
Nebula nebula;

//  IMMAGINE
ImageParticleSystem imgSystem;
float imgX, imgY, imgW, imgH; // rettangolo dove sta l'immagine


// ============================================================
// SETUP
// ============================================================
void setup() {
  fullScreen(P2D);

  oscP5 = new OscP5(this, port);
  pythonVoiceLocation = new NetAddress("127.0.0.1", 5006);

  myFont = createFont("Georgia", fontSize);
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);

  nebula = new Nebula();

  moodManager = new MoodManager("RELEASE");
  Atmosphere currentVals = moodManager.getCurrentVals();

  for (int i = 0; i < (int)currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }

  calcImageRect();
  imgSystem = new ImageParticleSystem();
}


// ============================================================
// DRAW
// ============================================================
void draw() {
  //  transizione mood 
  moodManager.update();
  Atmosphere currentVals = moodManager.getCurrentVals();

  // particelle bg: numero dinamico
  int targetCount = (int) currentVals.particleCount;
  while (bgParticles.size() < targetCount) bgParticles.add(new BgParticle());
  while (bgParticles.size() > targetCount) bgParticles.remove(0);

  // sfondo + nebula 
  background(currentVals.bgColor);
  nebula.draw(currentVals.nebulaColor, currentVals.nebulaAlphaMax, currentVals.nebulaSpeed);

  // particelle bg 
  for (BgParticle p : bgParticles) {
    p.update(currentVals.particleSpeedY, currentVals.chaos);
    p.display(currentVals.particleColor);
  }

  //  schermata iniziale attesa
  if (!isPlaying) {
    fill(255, 220);
    textAlign(CENTER, CENTER);
    textSize(fontSize + 22);
    text("BARD", width / 2.0, height / 2.0 - 36);
    textSize(fontSize - 8);
    text("I'll tell you a story...", width / 2.0, height / 2.0 + 42);
    textAlign(LEFT, CENTER);
    return;
  }

  // timer segmento
  if (millis() - lastSegmentTime > slideDuration * 1000) {
    loadNextSegment();
  }

  // immagine 
  imgSystem.updateAndDisplay(currentVals.chaos * 2);

  // testo 
  wordsystem.updateWordLogic();
  wordsystem.drawWords(currentVals);
}


// ============================================================
// LAYOUT
// ============================================================
void calcImageRect() {
  imgX = width  * imageMarginX;
  imgY = height * imageMarginTop;
  imgW = width  * (1.0 - 2 * imageMarginX);
  imgH = height * imageAreaRatio;
}


// ============================================================
// CAMBIO SEGMENTO
// ============================================================
void loadNextSegment() {
  currentSegmentIndex++;
  if (currentSegmentIndex >= playlist.size()) currentSegmentIndex = 0;

  Segmento seg = playlist.get(currentSegmentIndex);
  println(">>> SEGMENTO " + currentSegmentIndex + " | mood: " + seg.categoria);
  println(">>> TESTO: " + seg.testo);

  imgSystem.loadAndConvert(seg.imagePath, imgX, imgY, imgW, imgH);

  moodManager.setMood(seg.categoria);

  fullText = seg.testo;
  wordsystem.calculatePages();
  wordsystem.loadPage(0);

  OscMessage msgVoce = new OscMessage("/speak");
  msgVoce.add(seg.testo);
  oscP5.send(msgVoce, pythonVoiceLocation);

  lastSegmentTime = millis();

  calcImageRect();
 
}

// ============================================================
// OSC
// ============================================================
void oscEvent(OscMessage msg) {
  //oschandler.oscEvent(msg);
  println("OSC: " + msg.addrPattern());

    if (msg.checkAddrPattern("/config/duration")) {
      if (msg.checkTypetag("f"))      slideDuration = msg.get(0).floatValue();
      else if (msg.checkTypetag("i")) slideDuration = msg.get(0).intValue();
      println(">>> Durata slide: " + slideDuration);
      return;
    }
  
    if (msg.checkAddrPattern("/segment")) {
      String cat = msg.get(0).stringValue();
      String txt = msg.get(1).stringValue();
      String path = msg.get(2).stringValue();
      playlist.add(new Segmento(cat, txt, path));
      println(">>> Segmento aggiunto: " + cat + " | " + txt + " | " + path);
      return;
    }
  
  
    if (msg.checkAddrPattern("/start")) {
      if (playlist.size() > 0) {
        println(">>> START!");
        isPlaying       = true;
        lastSegmentTime = millis() - (int)(slideDuration * 1000);
      }
      return;
    }
}
    
