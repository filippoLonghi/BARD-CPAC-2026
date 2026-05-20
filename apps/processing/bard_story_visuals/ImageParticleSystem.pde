class ImageParticleSystem {
  ArrayList<PixelParticle> particles = new ArrayList<PixelParticle>();
  
  void loadAndConvert(String path, float rx, float ry, float rw, float rh) {
    PImage img = loadImage(path);
    if (img == null) return;
    
    img.resize(150, 0); // 150 pixel di larghezza, altezza proporzionale
    img.loadPixels();
    
    ArrayList<PVector> targets = new ArrayList<PVector>();
    ArrayList<Integer> colors = new ArrayList<Integer>();
    targets.clear();
    colors.clear();

    // Rapporto per scalare i pixel sull'area corretta dello schermo
    float sc = rw / img.width;
    float startX = rx + (rw - (img.width * sc)) / 2;
    float startY = ry + (rh - (img.height * sc)) / 2;

    for (int y = 0; y < img.height; y += 1) { // Saltiamo dei pixel per estetica
      for (int x = 0; x < img.width; x += 1) {
        color pix = img.pixels[x + y * img.width];
        if (alpha(pix) > 10 && brightness(pix) > 10) { // scarta il nero e il trasparente
          float tx = startX + x * sc;
          float ty = startY + y * sc;
          targets.add(new PVector(tx, ty));
          colors.add(pix);
        }
      }
    }
    
    int numNewTargets = targets.size();
    
    if (numNewTargets == 0) {
      println("ATTENZIONE: L'immagine è vuota o troppo scura. Abortisco il morphing.");
      return; // Esce dalla funzione ed evita la divisione per zero
    }
    // Se servono più particelle di quelle che abbiamo, creiamole "nel punto attuale"
    while (particles.size() < numNewTargets) {
      // Le nuove particelle nascono al centro o in un punto casuale per poi volare al target
      particles.add(new PixelParticle(width/2, height/2, color(0,0))); 
    }
    while (particles.size() > numNewTargets) {
      particles.remove(particles.size() - 1);
    }
    println("numero di particles %d", particles.size());

    // Riassegniamo TUTTE le particelle
    for (int i = 0; i < particles.size(); i++) {
      PixelParticle p = particles.get(i);
      int in = i % numNewTargets;
      p.setNewTarget(targets.get(in).x, targets.get(in).y, colors.get(in));
    }
  }
  
  

  void updateAndDisplay(float chaos) {    
    for (PixelParticle p : particles) {
      p.update(chaos);
      p.display(255); //cmabiato displayaplha con 255 non so perchè
    }
  }
  
}
