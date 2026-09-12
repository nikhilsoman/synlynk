const fs = require('fs');
const path = require('path');

module.exports = function(eleventyConfig) {
  eleventyConfig.setUseGitIgnore(false);

  // Dynamically copy docs/blog/*.md files into src/blog/posts/
  const sourceDir = path.join(__dirname, '../docs/blog');
  const targetDir = path.join(__dirname, 'src/blog/posts');

  if (fs.existsSync(sourceDir)) {
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }

    // Clear existing copied files in targetDir to avoid stale ones
    const existingFiles = fs.readdirSync(targetDir);
    for (const file of existingFiles) {
      if (file.endsWith('.md')) {
        fs.unlinkSync(path.join(targetDir, file));
      }
    }

    const files = fs.readdirSync(sourceDir);
    for (const file of files) {
      if (file.endsWith('.md') && file !== 'README.md') {
        fs.copyFileSync(path.join(sourceDir, file), path.join(targetDir, file));
      }
    }

    // Write posts.json directory data file
    const postsJsonPath = path.join(targetDir, 'posts.json');
    fs.writeFileSync(postsJsonPath, JSON.stringify({
      layout: "blog-post.njk",
      permalink: "/blog/{{ page.fileSlug }}/"
    }, null, 2));
  }

  // Dynamically copy docs/brainstorm/**/*.html files into src/assets/brainstorm/
  const brainstormSourceDir = path.join(__dirname, '../docs/brainstorm');
  const brainstormTargetDir = path.join(__dirname, 'src/assets/brainstorm');

  if (fs.existsSync(brainstormSourceDir)) {
    // Clear existing copied files in targetDir to avoid stale ones
    if (fs.existsSync(brainstormTargetDir)) {
      fs.rmSync(brainstormTargetDir, { recursive: true, force: true });
    }
    fs.mkdirSync(brainstormTargetDir, { recursive: true });

    function copyRecursive(src, dest) {
      const items = fs.readdirSync(src);
      for (const item of items) {
        const srcPath = path.join(src, item);
        const destPath = path.join(dest, item);
        const stat = fs.statSync(srcPath);
        if (stat.isDirectory()) {
          fs.mkdirSync(destPath, { recursive: true });
          copyRecursive(srcPath, destPath);
        } else if (stat.isFile() && item.endsWith('.html')) {
          fs.copyFileSync(srcPath, destPath);
        }
      }
    }
    copyRecursive(brainstormSourceDir, brainstormTargetDir);
  }

  // Dynamically copy and process CHANGELOG.md
  const changelogPath = path.join(__dirname, '../CHANGELOG.md');
  const targetChangelogPath = path.join(__dirname, 'src/changelog.md');
  if (fs.existsSync(changelogPath)) {
    let content = fs.readFileSync(changelogPath, 'utf-8');
    content = content.replace(/^# Changelog\r?\n/, '');

    // Replace version headers
    // Example: ## [0.9.8] - 2026-06-27
    content = content.replace(/##\s+\[([^\]]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})/g, (match, version, date) => {
      return `<div class="changelog-version-header"><span class="changelog-version">v${version}</span><span class="changelog-date">${date}</span></div>`;
    });

    // Replace section headers
    content = content.replace(/###\s+Added/gi, '<h3 class="tag-added">Added</h3>');
    content = content.replace(/###\s+Fixed/gi, '<h3 class="tag-fixed">Fixed</h3>');
    content = content.replace(/###\s+Changed/gi, '<h3 class="tag-changed">Changed</h3>');

    // Prepend frontmatter
    const frontmatter = `---\nlayout: changelog-layout.njk\ntitle: Changelog\n---\n\n`;
    fs.writeFileSync(targetChangelogPath, frontmatter + content);
  }

  // Helper: Extract true date defensively without leaking file mtime
  function getEffectiveDate(item) {
    if (item.data && item.data.date) {
      if (item.data.date instanceof Date) return item.data.date;
      const parsed = new Date(item.data.date + 'T00:00:00');
      if (!isNaN(parsed.getTime())) return parsed;
    }
    // Fallback: look for YYYY-MM-DD in raw content
    if (item.template && item.template.frontMatter && item.template.frontMatter.content) {
      const match = item.template.frontMatter.content.match(/\b(202[0-9]-[0-1][0-9]-[0-3][0-9])\b/);
      if (match) {
        const parsed = new Date(match[1] + 'T00:00:00');
        if (!isNaN(parsed.getTime())) return parsed;
      }
    }
    // Fallback to stable early project epoch rather than CI checkout mtime
    return new Date('2026-06-01T00:00:00');
  }

  // Filters
  eleventyConfig.addFilter("dateFilter", (date, item) => {
    let d = null;
    if (item && item.data && item.data.date) {
      d = item.data.date instanceof Date ? item.data.date : new Date(item.data.date + 'T00:00:00');
    } else if (date) {
      d = date instanceof Date ? date : new Date(date + 'T00:00:00');
    }
    if (!d || isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
  });

  // Passthrough copies
  eleventyConfig.addPassthroughCopy("src/assets");

  // Blog collections
  function sortPosts(posts) {
    return posts.sort((a, b) => {
      const dateA = getEffectiveDate(a);
      const dateB = getEffectiveDate(b);
      const diff = dateB - dateA;
      if (diff !== 0) return diff;
      const postA = parseInt(a.data && a.data.post ? a.data.post : 0, 10);
      const postB = parseInt(b.data && b.data.post ? b.data.post : 0, 10);
      return postB - postA;
    });
  }

  function isReleasePost(item) {
    const type = (item.data && item.data.type) || "";
    const tags = (item.data && item.data.tags) || [];
    const slug = item.fileSlug || "";
    return type === "release" || (Array.isArray(tags) && tags.includes("release")) || /v0\.\d+\.0/.test(slug);
  }

  // All posts
  eleventyConfig.addCollection("posts", (collectionApi) => {
    return sortPosts(collectionApi.getFilteredByGlob("src/blog/posts/*.md"));
  });

  // Tier 1: Strategic Named Release Posts
  eleventyConfig.addCollection("releasePosts", (collectionApi) => {
    const all = collectionApi.getFilteredByGlob("src/blog/posts/*.md");
    return sortPosts(all.filter(isReleasePost));
  });

  // Tier 2: Per-PR Engineering Build Diary Posts
  eleventyConfig.addCollection("prPosts", (collectionApi) => {
    const all = collectionApi.getFilteredByGlob("src/blog/posts/*.md");
    return sortPosts(all.filter(item => !isReleasePost(item)));
  });

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      data: "_data"
    },
    templateFormats: ["njk", "md", "html"],
    htmlTemplateEngine: "njk",
    markdownTemplateEngine: "njk"
  };
};

