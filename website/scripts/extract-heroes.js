/**
 * Blog Hero Image Capture Workflow
 * 
 * Each blog post in docs/blog/*.md references design decisions and brainstorm sessions.
 * This script documents the pipeline to capture and link representative visuals for each post.
 * 
 * Manual Workflow Steps:
 * ---------------------
 * 1. Identify the brainstorm visual for the blog post under docs/brainstorm/<topic>/.
 *    For example: docs/brainstorm/bs5-website-redesign/hero-v4.html
 * 
 * 2. Open the selected HTML file in a web browser.
 * 
 * 3. Use browser DevTools (Ctrl+Shift+I or Cmd+Opt+I) to capture a screenshot:
 *    - In Chrome/Firefox, open the Command Menu (Cmd+Shift+P / Ctrl+Shift+P).
 *    - Type "screenshot" and select "Capture node screenshot" (with the target element selected)
 *      or "Capture full size screenshot".
 *    - Alternatively, use a browser extension or external screenshot tool.
 * 
 * 4. Place the captured PNG image in the assets folder:
 *    Path: website/src/assets/blog-heroes/<post-slug>.png
 *    (Create the directory website/src/assets/blog-heroes/ if it doesn't exist yet).
 * 
 * 5. Update the mapping file at:
 *    Path: website/src/_data/blogHeroes.json
 * 
 *    Structure:
 *    {
 *      "post-slug": "assets/blog-heroes/filename.png"
 *    }
 * 
 *    Example:
 *    {
 *      "30-pr78-bs5-phase2-agy-templates": "assets/blog-heroes/30-pr78-bs5-phase2-agy-templates.png"
 *    }
 * 
 * Note: If no entry exists in blogHeroes.json, the blog card and post template
 * will automatically fall back to rendering a premium color-shifting gradient
 * displaying the post's sequence number (e.g. #30).
 */

console.log("This script describes the manual workflow for capturing blog hero images.");
console.log("Please read the comments in this file (website/scripts/extract-heroes.js) for instructions.");
