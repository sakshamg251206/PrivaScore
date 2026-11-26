/**
 * Every user-facing string (section 7.6). Components import from here; no inline copy.
 *
 * House rules: plain, specific, sentence case. No em dashes or en dashes (use a period, comma,
 * colon or parentheses; ranges use a hyphen). No exclamation marks. Verbatim policy quotes are
 * exempt and are never altered.
 *
 * What may and may not be claimed is section 9: no grades, no "safe"/"unsafe", no "compliant",
 * no confidence percentages, no single combined score.
 */

export const copy = {
  brand: "PrivaScore",

  hero: {
    headline: "What does this privacy policy actually say?",
    sub: "Paste the full text. PrivaScore checks 16 practices, quotes the exact sentences it relied on, and scores the policy.",
  },

  input: {
    label: "Privacy policy text",
    placeholder: "Paste the privacy policy text here",
    counter: (chars: string, minutes: string) => `${chars} characters · about ${minutes} min to read`,
    limit: (max: string) => `Limit ${max}`,
    tooShort: (min: string) => `Paste at least ${min} characters. A full privacy policy is usually much longer.`,
    tooLong: (max: string) => `This is over ${max} characters. Paste only the privacy policy.`,
    company: "Company name (optional)",
    scope: "Consumer AI product",
    scopeHelp: "Ignore terms that apply only to business or API customers.",
    submit: "Analyze policy",
    privacyNote: "The text is sent to Google's Gemini API for analysis. PrivaScore does not store or log it.",
    examplesHeading: "Or open a saved analysis",
  },

  examples: {
    heading: "Saved analyses",
    /**
     * Do NOT shorten this to "the same result you would get by pasting that text". It is not:
     * the provider is not guaranteed to be deterministic even at temperature 0, and this server
     * may be running a different model than the one that produced the stored run. The stored
     * result is evidence of what that run said, not a prediction of what a new run would say.
     */
    sub: "Fifteen real privacy policies, analysed earlier and stored with the run. Opening one costs no provider call, so it is instant. It shows the stored result: pasting the same text runs a fresh analysis, which can label some practices differently.",
    provenance: (model: string, date: string) => `Analysed by ${model} on ${date}.`,
    /** Neutral by design (section 9): this is the order of the gold set, not a ranking. */
    orderNote: "Listed in gold set order, which is not a ranking.",
    columnPolicy: "Policy",
    columnRisk: "Risk",
    columnQuality: "Quality",
    columnLength: "Length",
    open: (company: string) => `Open the saved analysis of ${company}`,
    chars: (chars: string) => `${chars} characters`,
    incomplete: "Incomplete",
    incompleteHelp: "Some practices could not be checked in this run.",
    unavailable: "Saved analyses are not available on this server.",
    loading: "Loading saved analyses",
    savedBadge: "Saved analysis",
    savedBanner: (company: string, model: string, date: string) =>
      `This is a saved analysis of ${company}'s privacy policy, produced by ${model} on ${date}. It was not run just now.`,
    backToStart: "Back to the start",
  },

  map: {
    heading: "Where the saved policies sit",
    sub: "Each point is one of the 15 saved policies. The axes are the two scores, which are read together and never combined.",
    xAxis: "Privacy Risk Index",
    yAxis: "Disclosure Quality",
    low: "lower",
    high: "higher",
    youAreHere: (company: string) => `${company}, the policy shown above`,
    thisPolicy: "This policy",
    savedPolicy: "Saved policy",
    pointLabel: (company: string, risk: number, quality: number) =>
      `${company}: risk ${risk}, disclosure quality ${quality}`,
    noteAxes: "The two axes measure different things. A policy can be high on both.",
  },

  loading: {
    title: "Reading the policy",
    steps: [
      "Splitting the text into numbered sentences",
      "Profiling paragraphs with the BERT classifier",
      "Asking Gemini about 16 practices",
      "Checking every quote word for word against your text",
      "Calculating the two scores",
    ],
    footer: "This usually takes a minute or two. Keep this tab open.",
    elapsed: (mmss: string) => `${mmss} elapsed`,
    stepsHeading: "What happens now",
    size: (words: string, minutes: string) =>
      `${words} words · about ${minutes} minutes to read in full`,
    cancel: "Cancel",
    slow: "Still working. Gemini can be slow under load.",
    verySlow: "This is taking unusually long. You can keep waiting or cancel.",
    started: "Analysis started",
    complete: "Analysis complete",
    reducedMotion: "Working…",
  },

  scores: {
    risk: "Privacy Risk Index",
    quality: "Disclosure Quality",
    riskDirection: "Lower means less exposure described.",
    qualityDirection: "Higher means more of the 16 practices are addressed clearly.",
    /** Two parts, because the count is bold and the instruction is not. */
    notStatedCount: (n: number, m: number) => `${n} of ${m}`,
    notStatedRest: "scored practices are not stated.",
    readTogether: "Read the two scores together.",
  },

  groups: {
    general: "General practices",
    ai: "AI practices",
    dpdp: "India DPDP readiness",
  },

  states: {
    ED: "Disclosed",
    CD: "Conditional",
    EE: "Excluded",
    NS: "Not stated",
    UN: "Unclear",
  },

  /** Risk marks are computed from risk_points / max_risk_points, never fixed per state. */
  riskMarks: {
    adds: "Adds risk",
    partly: "Partly adds risk",
    notStated: "Not stated",
    none: "No added risk",
    notScored: "Not scored",
  },

  status: {
    verified: "Every quote was found word for word in your text.",
    verified_partial: (n: number) =>
      `${n} quote${n === 1 ? "" : "s"} failed the word-for-word check and ${n === 1 ? "was" : "were"} dropped. The label passed its other checks.`,
    absent_unverifiable: (n: number) =>
      `Gemini found nothing on this in the ${n} sentences that matched its search terms. Absence can't be proven.`,
    no_candidates: (n: number) =>
      `No sentence matched any of the ${n} search terms for this practice, so it is marked Not stated without asking Gemini.`,
    not_applicable: "Only applies when the policy says it trains AI on user data (AI1). Not scored.",
    rejected: "No answer passed verification after a retry. Scored as Unclear, so the scores are incomplete.",
  },

  flagRow: {
    rationale: "Why:",
    evidence: (n: number) => `Evidence · ${n} verified quote${n === 1 ? "" : "s"}`,
    dropped: (n: number) =>
      `(${n} quote${n === 1 ? "" : "s"} failed the word-for-word check and ${n === 1 ? "was" : "were"} dropped)`,
    showInPolicy: "Show in policy",
    informational: "Informational. Not part of either score.",
    meaning: (label: string) => `${label} for this practice means:`,
    points: (r: number, mr: number, q: number, w: number) =>
      `Risk ${r} of ${mr} points · Quality ${q} of 2 points · Weight ${w}`,
  },

  errors: {
    /** Headings: the plain problem, then one sentence on what to do (section 7.4 D). */
    headings: {
      BUSY: "One analysis at a time",
      LLM_QUOTA: "Usage limit reached",
      LLM_OVERLOADED: "Gemini is busy",
      LLM_ERROR: "The analysis failed",
      NETWORK: "No connection to the server",
      TEXT_TOO_LONG: "That text is too long",
      TEXT_TOO_SHORT: "That text is too short",
      BODY_TOO_LARGE: "That text is too long",
      INVALID_REQUEST: "That request was not valid",
      NOT_FOUND: "Not found",
      INTERNAL: "Something went wrong",
      CANCELLED: "Something went wrong",
    },
    BUSY: "Another analysis is running. Try again in about a minute.",
    LLM_QUOTA:
      "Gemini's usage limit has been reached. This is a cap on analyses per day, so it may not reset for several hours \u2014 trying again shortly will not help. Open a saved analysis instead: all fifteen still work.",
    LLM_OVERLOADED: "Gemini is overloaded right now. Try again in a few minutes.",
    LLM_ERROR: "The analysis service failed. Nothing was saved. Try again.",
    BODY_TOO_LARGE: (max: string) => `This is over ${max} characters. Paste only the privacy policy.`,
    TEXT_TOO_LONG: (max: string) => `This is over ${max} characters. Paste only the privacy policy.`,
    TEXT_TOO_SHORT: (min: string) => `Paste at least ${min} characters. A full privacy policy is usually much longer.`,
    INVALID_REQUEST: "Something about that request was not valid. Try again.",
    NETWORK: "Couldn't reach the PrivaScore server. Check your connection and try again.",
    INTERNAL: "Something went wrong on our side. Nothing was saved. Try again.",
    tryAgain: "Try again",
    editText: "Edit text",
  },

  howToRead: {
    heading: "How to read these results",
    points: [
      "Both scores come from fixed rules applied to the 16 practices. They are not probabilities that a company misuses data.",
      "Not stated never adds risk. Silence lowers Disclosure Quality instead, so a low Risk Index with low Disclosure Quality means the policy says little, not that it is safe.",
      "Each practice is judged for a user in India. The DPDP practices check readiness under India's Digital Personal Data Protection Act 2023 and its Rules. They are not a legal compliance verdict.",
      "Quotes are checked word for word against your text. The check proves the words are there, not that the label is right.",
      "On a 15-policy reference set labelled by one annotator, the extractor's answer matched the reference on 183 of 210 checks.",
      "The category profile comes from a BERT classifier trained on 2016 website policies (OPP-115). It is descriptive and not part of the scores.",
      "Results describe the text you pasted, at the time you pasted it.",
    ],
  },

  results: {
    untitled: "Your policy",
    sourceLabel: "Your text",
    /** A saved analysis is a published policy, not something the reader pasted. */
    sourceLabelSaved: (company: string) => `${company}'s policy text`,
    analyzeAnother: "Analyze another policy",
    downloadJson: "Download JSON",
    bertHeading: "What the paragraphs are about",
    bertNote: "From a BERT classifier trained on 2016 website policies (OPP-115). A paragraph can count toward several categories, so the shares do not add up to 100%. Descriptive only: not part of the scores.",
    bertUnavailable: "The category profile isn't available on this server.",
    readingHeading: "How hard it is to read",
    vagueNote: "Cue categories from Bhatia et al. (2016). A cue is a hint of vague wording, not a judgement: nearby sentences can make it specific.",
    flagsHeading: "The 16 practices",
    incomplete: (ids: string[]) =>
      `${ids.length} practice${ids.length === 1 ? "" : "s"} couldn't be verified and ${ids.length === 1 ? "was" : "were"} scored as Unclear: ${ids.join(", ")}. The scores are incomplete.`,
  },

  footer:
    "PrivaScore is a student research project (LNMIIT). Code under the MIT License. The BERT model is trained on OPP-115, licensed for non-commercial research and teaching only.",

  nav: { howItWorks: "How it works", github: "GitHub" },
} as const;
