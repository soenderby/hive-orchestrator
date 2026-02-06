# The Rule of Five for LLM Review

## Overview

The **Rule of Five** is a structured approach to reviewing and refining outputs from large language models (LLMs). Rather than expecting a single generation to be perfect, the rule guides you through **five distinct passes** to improve quality systematically. This methodology ensures that outputs are not only correct but also clear, robust, and polished.

Although there is no universally standardized “Rule of Five” for LLMs in academic literature, this concept has been described in developer tooling communities (notably in a gist discussing iterative refinement for high-quality outputs) as a five-stage iterative refinement process that applies well across documents, code, analyses, and other AI-generated work. :contentReference[oaicite:0]{index=0}

---

## When to Use

Apply the Rule of Five when:

- You need outputs that are **production-ready** or shareable with clients or stakeholders.
- The task requires **high quality, accuracy, and robustness** rather than a quick answer.
- You want to ensure **comprehension, correctness, and completeness**.

Skip or simplify it for:
- Quick informational answers
- Exploratory brainstorming where polish isn’t necessary

---

## The Five Passes

### 1. Draft — *Shape and Coverage*

**Goal:** Create a complete first draft with broad coverage.

This pass prioritizes *breadth over depth*. Collect all relevant points, structure the content, and make sure nothing essential is missing. Don’t worry about perfection yet.

**Example prompt:**
> *“Generate an initial draft of the content on [topic/task]. Focus on covering all main sections and ideas.”*

Baseline output from this stage sets the scaffolding for later refinement.

---

### 2. Correctness — *Fact & Logic Checking*

**Goal:** Ensure the content is **accurate and logically sound**.

At this stage, review and correct errors. Check facts, verify any calculations or references, and fix logical inconsistencies.

**Example prompt:**
> *“Review the draft above and correct all factual or logical mistakes. Explain each correction.”*

This pass elevates the work from draft to **reliable information**.

---

### 3. Clarity — *Understandability & Structure*

**Goal:** Improve readability and clarity.

Rewrite the content to make it accessible and easy to follow. This includes simplifying language, improving transitions, reorganizing sections if needed, and removing jargon.

**Example prompt:**
> *“Rewrite the corrected content to improve clarity. Ensure it’s structured logically and easy to understand.”*

This pass focuses on how well a reader can *comprehend* the output.

---

### 4. Edge Cases — *Robustness & Gaps*

**Goal:** Identify missing considerations or unusual scenarios.

Look for potential blind spots, exceptions, limitations, and contexts that may not have been covered. Mention assumptions and how the solution behaves outside typical conditions.

**Example prompt:**
> *“Identify edge cases, exceptions, or limitations in the refined content and suggest how to address them.”*

This step increases resilience and usefulness in **real-world contexts**.

---

### 5. Excellence — *Polish & Professionalism*

**Goal:** Final polish to make the document **production-ready**.

This stage focuses on stylistic refinement, professional tone, consistency, and presentation quality. Remove redundancy, tighten language, improve headings, and format for readability.

**Example prompt:**
> *“Polish the refined content so it is professional, concise, and ready for final delivery.”*

Outputs from this stage should be suitable for publishing, sharing, or client delivery.

---

## Why This Works

Large language models often produce good content on the first pass, but not **excellent** content. Systematic refinement helps:

1. Catch and correct errors that simple prompting misses.
2. Clarify meaning and improve structure.
3. Surface gaps or edge conditions.
4. Produce professional-grade communication.

This iterative thinking mirrors how humans edit and refine their work — and helps compensate for inherent limitations in one-shot generation.

---

## Practical Tips

- Always **reference the previous pass** in your prompt so the model can incorporate context.
- You can loop specific passes (e.g., Correctness or Clarity) if needed — but try to avoid unbounded repetition.
- Use this framework for outputs that will be **consumed by others**, not just internal experimentation.

---

## Conclusion

The **Rule of Five for LLM Review** is a practical, repeatable approach for elevating LLM output quality. By separating concerns — from correctness and clarity through edge cases and final polish — this process transforms raw model responses into polished, trustworthy work suitable for real-world use. :contentReference[oaicite:1]{index=1}
