# synlynk.com Website Redesign (BS-5)

This is the source code for the standalone redesign of synlynk.com. It is built using Eleventy v3, Nunjucks, and Vanilla CSS/JS.

## Local Development

1. Navigate to the website folder:
   ```bash
   cd website
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the local development server (runs on port 8081):
   ```bash
   npm run serve
   ```

4. Build the production site (outputs to `_site/`):
   ```bash
   npm run build
   ```

## Sourcing Blog Posts

Blog posts are written as markdown files inside the root directory `docs/blog/` (single source of truth).
At config time, `.eleventy.js` automatically copies these markdown files into `website/src/blog/posts/` and registers them as the Eleventy `posts` collection.
The `src/blog/posts/` directory is ignored by git to prevent committing duplicate files.

## Blog Hero Images Pipeline

To display custom screenshots or architecture diagrams for a blog post:

1. Identify the matching brainstorm visual under `docs/brainstorm/<topic>/` (e.g. `docs/brainstorm/bs5-website-redesign/hero-v4.html`).
2. Open the HTML file in a web browser.
3. Capture a screenshot (e.g., using DevTools -> Command Menu -> "Capture node screenshot" on the main container).
4. Save the image as a PNG at `website/src/assets/blog-heroes/<post-slug>.png`.
5. Open `website/src/_data/blogHeroes.json` and add a mapping:
   ```json
   {
     "post-slug": "assets/blog-heroes/filename.png"
   }
   ```

### Gradient Fallbacks
If a post does not have a mapped hero image in `blogHeroes.json`, the templates automatically render a premium color-shifting gradient containing the post's sequence number (e.g. `#30`).
