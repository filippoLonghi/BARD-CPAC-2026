class ImageParticleSystem {
  final int maxParticles = 12000;
  ArrayList<PixelParticle> particles = new ArrayList<PixelParticle>();
  float displayAlpha = 255;
  float revealAtSeconds = 0; //tolgo?

  void loadAndConvert(String path, float rx, float ry, float rw, float rh, String role) {
    PImage img = loadImage(path);
    if (img == null) return;

    boolean keepDarkPixels = role.equals("background");
    displayAlpha = role.equals("background") ? 125 : (role.equals("symbol") ? 215 : 255);
    img.resize(400, 0);
    img.loadPixels();
    int sampleStep = max(1, ceil(sqrt((img.width * img.height) / (float)maxParticles)));

    ArrayList<PVector> targets = new ArrayList<PVector>();
    ArrayList<Integer> colors = new ArrayList<Integer>();

    float sc = min(rw / img.width, rh / img.height);
    float startX = rx + (rw - img.width * sc) / 2;
    float startY = ry + (rh - img.height * sc) / 2;

    for (int y = 0; y < img.height; y += sampleStep) {
      for (int x = 0; x < img.width; x += sampleStep) {
        color pixelColor = img.pixels[x + y * img.width];
        if (alpha(pixelColor) > 10 && (keepDarkPixels || brightness(pixelColor) > 10)) {
          targets.add(new PVector(startX + x * sc, startY + y * sc));
          colors.add(pixelColor);
        }
      }
    }

    if (targets.size() == 0) {
      println(">>> Image has no usable pixels: " + path);
      return;
    }

    while (particles.size() < targets.size()) {
      particles.add(new PixelParticle(width / 2, height / 2, color(0, 0)));
    }
    while (particles.size() > targets.size()) {
      particles.remove(particles.size() - 1);
    }

    for (int i = 0; i < particles.size(); i++) {
      PVector target = targets.get(i);
      particles.get(i).setNewTarget(target.x, target.y, colors.get(i));
    }
  }

  void updateAndDisplay(float chaos) {
    //if (performanceElapsedSeconds() < revealAtSeconds) return;
    for (PixelParticle particle : particles) {
      particle.update(chaos);
      particle.display(displayAlpha);
    }
  }
}
