/*class ImageParticleSystem {
  final int maxParticles = 12000;
  ArrayList<PixelParticle> particles = new ArrayList<PixelParticle>();
  float displayAlpha = 255;
  float revealAtSeconds = 0; //tolgo?

  void loadAndConvert(String path, float rx, float ry, float rw, float rh, String role) {
    PImage img = loadImage(path);
    if (img == null) return;

    //boolean keepDarkPixels = role.equals("background");
    displayAlpha = role.equals("background") ? 125 : (role.equals("symbol") ? 215 : 255);
    img.resize(400, 0);
    img.loadPixels();
    boolean[] bgMask = calculateFloodFillMask(img);
    int sampleStep = max(1, ceil(sqrt((img.width * img.height) / (float)maxParticles)));

    ArrayList<PVector> targets = new ArrayList<PVector>();
    ArrayList<Integer> colors = new ArrayList<Integer>();

    float sc = min(rw / img.width, rh / img.height);
    float startX = rx + (rw - img.width * sc) / 2;
    float startY = ry + (rh - img.height * sc) / 2;

    for (int y = 0; y < img.height; y += sampleStep) {
      for (int x = 0; x < img.width; x += sampleStep) {
        int idx = x + y * img.width;
        color pixelColor = img.pixels[idx];
        
        // Se il pixel non è trasparente, E non è stato divorato dalla maschera magica, diventa una particella!
        if (alpha(pixelColor) > 10 && !bgMask[idx]) {
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
}*/

class ImageParticleSystem {
  final int maxParticles = 15000;
  ArrayList<PixelParticle> particles = new ArrayList<PixelParticle>();
  float displayAlpha = 255;

  void loadAndConvert(String path, float rx, float ry, float rw, float rh, String role) {
    PImage img = loadImage(path);
    if (img == null) return;

    boolean isBackground = role.equals("background");
    displayAlpha = isBackground ? 125 : (role.equals("symbol") ? 215 : 255);
    
    img.resize(700, 0);
    img.loadPixels();
    
    // Applichiamo la bacchetta magica SOLO a soggetti e simboli
    boolean[] bgMask = null;
    if (!isBackground) {
      bgMask = calculateFloodFillMask(img);
    }

    int sampleStep = max(1, ceil(sqrt((img.width * img.height) / (float)maxParticles)));

    ArrayList<PVector> targets = new ArrayList<PVector>();
    ArrayList<Integer> colors = new ArrayList<Integer>();

    float sc = min(rw / img.width, rh / img.height);
    float startX = rx + (rw - img.width * sc) / 2;
    float startY = ry + (rh - img.height * sc) / 2;
    
    // Calcoliamo i margini da tagliare per lo sfondo (il 4% del bordo)
    int marginX = (int)(img.width * 0.04);
    int marginY = (int)(img.height * 0.04);

    for (int y = 0; y < img.height; y += sampleStep) {
      for (int x = 0; x < img.width; x += sampleStep) {
        
        // IL RITAGLIO: Se è uno sfondo, ignoriamo il pixel se si trova nel bordo esterno (le cornici)
        if (isBackground) {
          if (x < marginX || x > img.width - marginX || y < marginY || y > img.height - marginY) {
            continue; 
          }
        }

        int idx = x + y * img.width;
        color pixelColor = img.pixels[idx];
        
        if (isBackground) {
          // Per lo sfondo salviamo tutto (cieli neri compresi), basta che non sia trasparente
          if (alpha(pixelColor) > 10) {
            targets.add(new PVector(startX + x * sc, startY + y * sc));
            colors.add(pixelColor);
          }
        } else {
          // Per soggetti e simboli usiamo il risultato della bacchetta magica! 
          // (E aggiungiamo un controllo di sicurezza brightness > 8 per piccoli rimasugli di ombre ai bordi)
          if (alpha(pixelColor) > 10 && !bgMask[idx] && brightness(pixelColor) > 8) {
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

    // Riciclo particelle (così non appesantiamo la memoria)
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
