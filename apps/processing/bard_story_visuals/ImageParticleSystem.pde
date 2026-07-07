class ImageParticleSystem {
  /* classe per caricare le immagini e proiettarle come particelle*/
  final int maxParticles = 15000;
  ArrayList<PixelParticle> particles = new ArrayList<PixelParticle>();
  float displayAlpha = 255;

  void loadAndConvert(String path, float rx, float ry, float rw, float rh, String role) {
    PImage img = loadImage(path);
    if (img == null) return;

    img = autoCropFrames(img);

    boolean isBackground = role.equals("background");
    displayAlpha = isBackground ? 150 : 255; // 150 livello di opacità del background

    if (isBackground) {
      img.resize(1200, 0);
    } else {
      img.resize(500, 0);
    }

    img.loadPixels();
    boolean hasAlphaCutout = hasTransparentPixels(img);

    boolean[] bgMask = null;
    if (!isBackground && !hasAlphaCutout) {
      bgMask = calculateFloodFillMask(img);
    }

    int sampleStep = max(1, ceil(sqrt((img.width * img.height) / (float)maxParticles)));

    ArrayList<PVector> targets = new ArrayList<PVector>();
    ArrayList<Integer> colors = new ArrayList<Integer>();

    float sc = min(rw / img.width, rh / img.height);
    float startX = rx + (rw - img.width * sc) / 2;
    float startY = ry + (rh - img.height * sc) / 2;

    int marginX = (int)(img.width * 0.04);
    int marginY = (int)(img.height * 0.04);

    for (int y = 0; y < img.height; y += sampleStep) {
      for (int x = 0; x < img.width; x += sampleStep) {
        if (isBackground) {
          if (x < marginX || x > img.width - marginX || y < marginY || y > img.height - marginY) {
            continue;
          }
        }

        int idx = x + y * img.width;
        color pixelColor = img.pixels[idx];

        if (isBackground) {
          if (alpha(pixelColor) > 10) {
            targets.add(new PVector(startX + x * sc, startY + y * sc));
            colors.add(pixelColor);
          }
        } else {
          if (alpha(pixelColor) > 10 && (bgMask == null || !bgMask[idx])) {
            targets.add(new PVector(startX + x * sc, startY + y * sc));
            colors.add(pixelColor);
          }
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
    for (PixelParticle particle : particles) {
      particle.update(chaos);
      particle.display(displayAlpha);
    }
  }
}
