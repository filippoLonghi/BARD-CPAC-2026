class Nebula {
  PGraphics canvas;
  float noiseScale = 0.003f;
  float timeZ = 0;

  Nebula() {
    canvas = createGraphics(width/4, height/4, P2D);
  }

  void draw(color c, float maxAlpha, float speed) { //draw chiamato nel draw principale 
    timeZ += speed;
    canvas.beginDraw();
    canvas.loadPixels();
    float r = red(c), g = green(c), b = blue(c);
    
    for (int x = 0; x < canvas.width; x++) { 
      for (int y = 0; y < canvas.height; y++) {
        float n1  = noise(x * noiseScale, y * noiseScale, timeZ); // perlin noise
        float n2  = noise(x * noiseScale * 2.5f + 100, y * noiseScale * 2.5f + 100, timeZ * 1.5f);
        float fin = pow(lerp(n1, n2, 0.4f), 3.0f);
        float a   = constrain(map(fin, 0, 0.8f, 0, maxAlpha), 0, maxAlpha);
        canvas.pixels[x + y * canvas.width] = color(r, g, b, a);
      }
    }
    canvas.updatePixels();
    canvas.endDraw();

    blendMode(BLEND);
    image(canvas, 0, 0, width*2, height*4);
    blendMode(BLEND);
  }
}
