module.exports = function(eleventyConfig) {
  // Filters
  eleventyConfig.addFilter("dateFilter", (date) => {
    const d = date instanceof Date ? date : new Date(date + 'T00:00:00');
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
  });

  // Passthrough copies
  eleventyConfig.addPassthroughCopy("src/assets");

  // Blog collection stub (wired to docs/blog in later phases)
  eleventyConfig.addCollection("posts", (collectionApi) => {
    // Placeholder: real posts pulled via glob or data in Phase 3+
    return collectionApi.getFilteredByGlob("src/blog/*.md").reverse();
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
