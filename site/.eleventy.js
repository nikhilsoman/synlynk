module.exports = function(eleventyConfig) {
  // Filters
  eleventyConfig.addFilter("dateFilter", (date) => {
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit"
    });
  });

  // Returns true if a feature (introduced at `introduced` minor) is available in release `minor`
  eleventyConfig.addFilter("featureAvailable", (introduced, minor) => {
    return parseFloat(introduced) <= parseFloat(minor);
  });

  // Returns only the releases where in_window is true, in array order
  eleventyConfig.addFilter("windowReleases", (releases) => {
    return releases.filter(r => r.in_window);
  });

  // Returns items from arr where item[key] === value
  eleventyConfig.addFilter("filterBy", (arr, key, value) => {
    return arr.filter(item => item[key] === value);
  });

  // Returns first item from arr where item[key] === value, or null
  eleventyConfig.addFilter("findBy", (arr, key, value) => {
    return arr.find(item => item[key] === value) || null;
  });

  // Passthrough copies
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addPassthroughCopy({"../docs/img/logo": "assets/img/logo"});

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
