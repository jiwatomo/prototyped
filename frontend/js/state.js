/* Small shared state container. Every mutation is explicit and local to the demo. */
const State = {
  profile: null,
  analysis: null,
  recommendations: null,
  extraction: null,
  pendingExtractions: new Set(),
  editingFacts: false,

  setProfile(profile) {
    this.profile = profile;
    return profile;
  },

  setAnalysis(analysis) {
    this.analysis = analysis;
    return analysis;
  },

  setRecommendations(payload) {
    this.recommendations = payload;
    return payload;
  },

  setExtraction(extraction) {
    this.extraction = extraction;
    return extraction;
  },

  confirmedTags() {
    if (!this.profile || !Array.isArray(this.profile.tags)) return [];
    return this.profile.tags.filter((tag) => tag.confirmation_status === "confirmed");
  },
};
