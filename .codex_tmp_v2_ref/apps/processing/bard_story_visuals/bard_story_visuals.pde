import java.util.HashMap;
import java.text.Normalizer;
import oscP5.*;
import netP5.*;
import java.net.URLDecoder; // decoder per i caratteri accentati 

OscP5 oscP5;
int port = 5005;
NetAddress pythonVoiceLocation;
NetAddress pythonReadyLocation;

float imageAreaRatio = 0.55;
float imageMarginX = 0.2;
float imageMarginTop = 0.13;
float textAreaPad = 32;

int fontSize = 20;
float leading = fontSize * 1.45;
PFont myFont;
String fullText = "";

WordsSystem wordsystem = new WordsSystem();
ArrayList<BgParticle> bgParticles = new ArrayList<BgParticle>();
MoodManager moodManager;
Nebula nebula;
HashMap<String, ImageParticleSystem> imgSystems = new HashMap<String, ImageParticleSystem>();

float imgX, imgY, imgW, imgH;

OscHandler oscHandler;
StoryDirector director;

String processingAudioPath = "";
ProcessingAudioPlayer processingAudioPlayer = new ProcessingAudioPlayer();


// ---------- SETUP -------------
void setup() {
  fullScreen(P2D);

  oscP5 = new OscP5(this, port);
  pythonVoiceLocation = new NetAddress("127.0.0.1", 5006);
  pythonReadyLocation = new NetAddress("127.0.0.1", 5007);
  
  myFont = createFont("Arial", fontSize, true, buildItalianCharset());
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);

  nebula = new Nebula();
  moodManager = new MoodManager("CALM");

  oscHandler = new OscHandler();
  director = new StoryDirector();

  Atmosphere currentVals = moodManager.getCurrentVals();
  for (int i = 0; i < (int)currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }

  calcImageRect();
}


// ---------- DRAW -------------
void draw() {
  if (director != null && director.isPlaying) {
    director.advanceTimeline();
    director.updateTimedMood();
  }

  moodManager.update();
  Atmosphere currentVals = moodManager.getCurrentVals();

  int targetCount = (int)currentVals.particleCount;
  while (bgParticles.size() < targetCount) bgParticles.add(new BgParticle());
  while (bgParticles.size() > targetCount) bgParticles.remove(0);

  background(currentVals.bgColor);
  nebula.draw(currentVals.nebulaColor, currentVals.nebulaAlphaMax, currentVals.nebulaSpeed);

  for (BgParticle particle : bgParticles) {
    particle.update(currentVals.particleSpeedY, currentVals.chaos);
    particle.display(currentVals.particleColor);
  }

  // testata iniziale prima che parta la storia
  if (!director.isPlaying) {
    fill(255, 220);
    textAlign(CENTER, CENTER);
    textSize(fontSize + 22);
    text("BARD", width / 2.0, height / 2.0 - 36);
    textSize(fontSize - 8);
    text("I'll tell you a story...", width / 2.0, height / 2.0 + 42);
    textAlign(LEFT, CENTER);
    return;
  }
  
  director.applyPendingImageReload();
  
  if (director.isOutro) { //se è finito fa la schermata di fine 
    fill(currentVals.textColor); // Usa il colore di testo armonioso del mood
    textAlign(CENTER, CENTER);
    textSize(fontSize + 14);
    text("The End", width / 2.0, height / 2.0);
    textAlign(LEFT, CENTER);
    
  } else { // scorre il tempo e controlla se c'è da cambiare
    updateCurrentSegmentImage(currentVals);
    wordsystem.updateWordLogic();
    wordsystem.drawWords(currentVals);
  }
}


// ------ gestione immagini ------

void updateCurrentSegmentImage(Atmosphere currentVals) {
  if (!director.isPlaying || director.currentSegmentIndex < 0 || director.currentSegmentIndex >= director.playlist.size()) return;
  
  // Disegniamo con un ordine fisso per avere la giusta profondità
  String[] drawOrder = {"background", "subject", "symbol"};
  
  for (String role : drawOrder) {
    if (imgSystems.containsKey(role)) {
      imgSystems.get(role).updateAndDisplay(currentVals.chaos * 2);
    }
  }
}


void loadSegmentImages(Segmento segment) {
  for (int position = 0; position < segment.imageCount(); position++) {
    ImageLayer layer = segment.imageLayerAt(position);
    if (layer == null || layer.path == null || layer.path.length() == 0) continue;

    String role = layer.role;
    
    // Se è la prima volta che incontriamo questo ruolo, creiamo il suo sciame di particelle
    if (!imgSystems.containsKey(role)) {
      imgSystems.put(role, new ImageParticleSystem());
    }

    // Peschiamo il sistema GIUSTO in base al nome
    ImageParticleSystem system = imgSystems.get(role);

    float rx = 0;
    float ry = 0;
    float rw = width;
    float rh = height;

    if (role.equals("background")) {
      rx = 0;
      ry = 0;
      rw = width;
      rh = height;
    } else if (role.equals("subject")) {
      rw = width * 0.36f;
      rh = height * 0.55f;
      rx = width * 0.58f; 
      ry = height * 0.38f;
    } else if (role.equals("symbol")) {
      rw = width * 0.16f;
      rh = height * 0.22f;
      rx = width * 0.42f;
      ry = height * 0.10f;
    }

    // Le vecchie particelle ricevono le nuove coordinate e i nuovi colori!
    system.loadAndConvert(layer.path, rx, ry, rw, rh, role);
  }
}

// ------------ OSC ------------
void oscEvent(OscMessage message) {
  // gestone delegata alla classe OSC handler 
  if (oscHandler != null) {
    oscHandler.handleMessage(message);
  }
}
