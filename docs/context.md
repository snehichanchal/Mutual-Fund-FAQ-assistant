# Project Context: Mutual Fund FAQ Assistant

## 🎯 What is This Project?

A **facts-only FAQ assistant** for mutual fund schemes, built in the context of [Groww](https://groww.in/) as the reference product. It answers objective, verifiable queries about mutual funds using **only official public sources** (AMC websites, AMFI, SEBI).

> **Core Principle:** No investment advice, no opinions, no recommendations — only verified facts with source citations.

---

## 🏗️ Architecture

The system uses a **lightweight Retrieval-Augmented Generation (RAG)** pipeline:

1. **Curated Corpus** → Official documents from a selected AMC (factsheets, KIM, SID, FAQ pages, SEBI/AMFI guidance)
2. **Retrieval** → Relevant chunks are fetched from the corpus based on user queries
3. **Generation** → An LLM generates concise, source-backed answers constrained to facts only

---

## 👥 Target Users

- **Retail investors** comparing mutual fund schemes
- **Customer support / content teams** handling repetitive mutual fund queries

---

## 📦 Scope of Work

### 1. Corpus Definition

| Requirement | Details |
|---|---|
| AMC Selection | **HDFC Asset Management Company** |
| Scheme Selection | - [HDFC Gold ETF Fund of Fund Direct Plan Growth](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth)<br>- [HDFC Large Cap Fund Direct Growth](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth)<br>- [HDFC Small Cap Fund Direct Growth](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth)<br>- [HDFC Silver ETF FOF Direct Growth](https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth)<br>- [HDFC Mid Cap Fund Direct Growth](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| Source URLs | **15–25** official public URLs |

**Source types to collect:**
- Scheme factsheets
- KIM (Key Information Memorandum)
- SID (Scheme Information Document)
- AMC FAQ / help pages
- AMFI / SEBI guidance pages
- Statement and tax document download guides

### 2. FAQ Assistant — Answerable Queries

The assistant must handle **facts-only queries** such as:

- Expense ratio of a scheme
- Exit load details
- Minimum SIP amount
- ELSS lock-in period
- Riskometer classification
- Benchmark index
- Process to download statements or capital gains reports

### 3. Response Format Rules

| Rule | Requirement |
|---|---|
| Length | Maximum **3 sentences** per response |
| Citation | Exactly **1 citation link** per response |
| Footer | `"Last updated from sources: <date>"` |

### 4. Refusal Handling

The assistant must **refuse** non-factual or advisory queries, such as:
- *"Should I invest in this fund?"*
- *"Which fund is better?"*

Refusal responses must:
- Be polite and clearly worded
- Reinforce the facts-only limitation
- Provide a relevant educational link (e.g., AMFI or SEBI resource)

### 5. User Interface (Minimal)

- A **welcome message**
- **Three example questions**
- A visible disclaimer: `"Facts-only. No investment advice."`

---

## 🚫 Constraints

### Data & Sources
- Use **only official public sources** (AMC, AMFI, SEBI)
- **No** third-party blogs or aggregator websites

### Privacy & Security — Do NOT Collect/Store/Process:
- PAN or Aadhaar numbers
- Account numbers
- OTPs
- Email addresses or phone numbers

### Content Restrictions
- **No** investment advice or recommendations
- **No** performance comparisons or return calculations
- For performance queries → provide a link to the official factsheet only

### Transparency
- Responses must be **short, factual, and verifiable**
- Every answer must include a **source link** and **last updated date**

---

## ✅ Success Criteria

1. Accurate retrieval of factual mutual fund information
2. Strict adherence to facts-only responses
3. Consistent inclusion of valid source citations
4. Proper refusal of advisory queries
5. Clean, minimal, and user-friendly interface

---

## 📄 Expected Deliverables

| Deliverable | Details |
|---|---|
| **README** | Setup instructions, selected AMC & schemes, architecture overview (RAG approach), known limitations |
| **Disclaimer** | `"Facts-only. No investment advice."` |
| **Working Assistant** | RAG-based Q&A with UI, refusal handling, and citation support |

---

## 💡 Summary

> Build a **trustworthy, transparent, and compliant** mutual fund FAQ assistant that prioritizes **accuracy over intelligence**. Users receive only verified, source-backed financial information — without any advisory bias or speculative content.
