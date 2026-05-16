class ImageLayer {
  int layerIndex;
  String role;
  String path;
  PImage img;
  PGraphics blurred;
  boolean attemptedLoad = false;
  
  ImageLayer(int idx, String r, String p) {
    layerIndex = idx;
    role = r;
    path = p;
  }
  
  void loadIfNeeded() {
    if (attemptedLoad) return;
    attemptedLoad = true;
    img = loadImage(path);
    if (img == null) {
      println(">>> Could not load image: " + path);
      return;
    }
    println(">>> Loaded image: " + path);
    
    if (role.equals("background")) {
      blurred = createGraphics(width, height, P2D);
      blurred.beginDraw();
      blurred.background(0);
      drawCover(blurred, img);
      blurred.filter(BLUR, 5);
      blurred.endDraw();
    }
  }
  
  void displayBackground() {
    loadIfNeeded();
    if (img == null) return;
    pushStyle();
    tint(255, 70);
    if (blurred != null) image(blurred, 0, 0, width, height);
    else image(img, 0, 0, width, height);
    noTint();
    popStyle();
  }
  
  void displayOverlay(float phase) {
    loadIfNeeded();
    if (img == null) return;
    pushStyle();
    float alphaVal = role.equals("symbol") ? 115 : 95;
    tint(255, alphaVal);
    imageMode(CENTER);
    
    float maxW = role.equals("symbol") ? width * 0.28 : width * 0.42;
    float maxH = role.equals("symbol") ? height * 0.28 : height * 0.46;
    float scaleVal = min(maxW / img.width, maxH / img.height);
    float drawW = img.width * scaleVal;
    float drawH = img.height * scaleVal;
    
    float x = role.equals("symbol") ? width * 0.72 : width * 0.5;
    float y = role.equals("symbol") ? height * 0.32 : height * 0.52;
    y += sin(phase + layerIndex) * 18;
    image(img, x, y, drawW, drawH);
    imageMode(CORNER);
    noTint();
    popStyle();
  }
}

class Segmento {
  int id;
  String categoria;
  String testo;
  ArrayList<ImageLayer> imageLayers;
  
  Segmento(int segmentId, String c, String t) {
    id = segmentId;
    categoria = c;
    testo = t;
    imageLayers = new ArrayList<ImageLayer>();
  }
  
  void addImage(int layerIndex, String role, String path) {
    imageLayers.add(new ImageLayer(layerIndex, role, path));
  }
}

void drawCover(PGraphics target, PImage source) {
  float scaleVal = max((float)target.width / source.width, (float)target.height / source.height);
  float drawW = source.width * scaleVal;
  float drawH = source.height * scaleVal;
  float x = (target.width - drawW) / 2.0;
  float y = (target.height - drawH) / 2.0;
  target.image(source, x, y, drawW, drawH);
}
