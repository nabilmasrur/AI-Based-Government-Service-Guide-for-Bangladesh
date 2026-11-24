import os
import subprocess
from pathlib import Path

html_content = """<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="utf-8">
<title>সেবা সহায়ক — Complete Project Guide (Zero to Hero)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page {
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
    @bottom-right {
      content: "পৃষ্ঠা " counter(page);
      font-family: 'Manrope', 'Hind Siliguri', sans-serif;
      font-size: 9pt;
      color: #718096;
    }
    @bottom-left {
      content: "সেবা সহায়ক — BAUST CSE 3202 AI Sessional Project Guide";
      font-family: 'Manrope', 'Hind Siliguri', sans-serif;
      font-size: 9pt;
      color: #718096;
    }
  }

  body {
    font-family: 'Hind Siliguri', 'Nirmala UI', 'Segoe UI', sans-serif;
    color: #1a202c;
    line-height: 1.6;
    font-size: 10.5pt;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }

  .ui-font { font-family: 'Manrope', sans-serif; }
  .code-font { font-family: 'IBM Plex Mono', monospace; font-size: 9pt; }

  /* Cover / Title Box */
  .cover-box {
    border: 2px solid #00875a;
    border-radius: 12px;
    padding: 30px;
    background: linear-gradient(135deg, #f0fdf4 0%, #e6fffa 100%);
    margin-bottom: 25px;
    box-shadow: 0 4px 15px rgba(0, 135, 90, 0.08);
  }

  .main-title {
    font-size: 26pt;
    font-weight: 800;
    color: #006946;
    margin: 0 0 6px 0;
    line-height: 1.25;
  }

  .sub-title {
    font-size: 13pt;
    font-weight: 600;
    color: #2d3748;
    margin: 0 0 15px 0;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    background: rgba(255, 255, 255, 0.9);
    padding: 12px 18px;
    border-radius: 8px;
    border: 1px solid #c6f6d5;
    font-size: 9.5pt;
  }

  .meta-item b { color: #006946; }

  /* Headings */
  h1 {
    font-size: 16pt;
    color: #006946;
    border-bottom: 2px solid #00875a;
    padding-bottom: 5px;
    margin-top: 28px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }

  h2 {
    font-size: 13pt;
    color: #2c7a7b;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }

  h3 {
    font-size: 11pt;
    color: #2d3748;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }

  p { margin: 0 0 10px 0; text-align: justify; }

  /* Callout Boxes */
  .box {
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 10pt;
    page-break-inside: avoid;
  }

  .box-green {
    background-color: #f0fff4;
    border-left: 4px solid #38a169;
    color: #22543d;
  }

  .box-blue {
    background-color: #ebf8ff;
    border-left: 4px solid #3182ce;
    color: #2a4365;
  }

  .box-amber {
    background-color: #fffaf0;
    border-left: 4px solid #dd6b20;
    color: #7b341e;
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
  }

  th {
    background-color: #00875a;
    color: white;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #00875a;
  }

  td {
    padding: 7px 10px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
  }

  tr:nth-child(even) td { background-color: #f7fafc; }

  /* Code & Pre */
  code {
    font-family: 'IBM Plex Mono', monospace;
    background: #edf2f7;
    padding: 2px 5px;
    border-radius: 4px;
    color: #b83280;
    font-size: 9pt;
  }

  pre {
    background: #1a202c;
    color: #f7fafc;
    padding: 12px;
    border-radius: 8px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8.5pt;
    overflow-x: auto;
    line-height: 1.45;
    margin: 10px 0;
    page-break-inside: avoid;
  }

  pre code {
    background: transparent;
    color: inherit;
    padding: 0;
  }

  .badge {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
  }
  .badge-fast { background: #c6f6d5; color: #22543d; }
  .badge-llm { background: #bee3f8; color: #2a4365; }

  .page-break { page-break-before: always; }
  ul, ol { margin: 0 0 10px 0; padding-left: 22px; }
  li { margin-bottom: 4px; }
</style>
</head>
<body>

<!-- Cover Section -->
<div class="cover-box">
  <div class="main-title">সেবা সহায়ক — Government Service Assistant</div>
  <div class="sub-title">AI-Based Conversational Goal-Based Agent for Public Services in Bangladesh</div>
  <div class="meta-grid">
    <div class="meta-item"><b>কোর্স:</b> CSE 3202 — Artificial Intelligence Sessional</div>
    <div class="meta-item"><b>প্রতিষ্ঠান:</b> Bangladesh Army University of Science and Technology (BAUST)</div>
    <div class="meta-item"><b>লেভেল/টার্ম:</b> Level 3, Term II</div>
    <div class="meta-item"><b>ডেভেলপার:</b> Md Lemmon Islam Bappy (GitHub: <code>bappy-81</code>)</div>
  </div>
</div>

<div class="box box-green">
  <strong>📌 গাইডের মূল উদ্দেশ্য:</strong> এই ডকুমেন্টে প্রজেক্টের শুরু থেকে শেষ পর্যন্ত সম্পূর্ণ আর্কিটেকচার, ডেটাফ্লো, প্রতিটা ফাইল ও কোডের ভূমিকা, সেটআপ গাইড এবং ভাইভাতে করা সম্ভাব্য সকল প্রশ্নের আদর্শ উত্তর সহজ ভাষায় ব্যাখ্যা করা হয়েছে যেন যেকোনো প্রেজেন্টেশন বা ভাইভায় ১০০% প্রস্তুতি থাকে।
</div>

<!-- Chapter 1 -->
<h1>অধ্যায় ১: প্রজেক্টের ধারণা ও দর্শন (Project Concept & Core Philosophy)</h1>

<p>
  <strong>সেবা সহায়ক</strong> হলো একটি গোল-বেসড (Goal-based) এআই এজেন্ট, যা বাংলাদেশের সাধারণ নাগরিকদের <strong>পাসপোর্ট</strong> এবং <strong>ড্রাইভিং লাইসেন্স</strong> সংক্রান্ত জটিল সরকারি নিয়মাবলী, ফি, প্রয়োজনীয় কাগজপত্র, সময়সীমা এবং আঞ্চলিক অফিস সম্পর্কিত প্রশ্নের সহজ, নির্ভুল এবং দ্রুততম সমাধান দেয়।
</p>

<h2>১.১ কেন এটি সাধারণ চ্যাটবট নয়, বরং একটি 'Goal-Based Agent'?</h2>
<p>
  একটি সাধারণ চ্যাটবট কেবল বর্তমান প্রম্পটের উপর ভিত্তি করে টেক্সট জেনারেট করে। কিন্তু <em>সেবা সহায়ক</em> ইউজারের একটি চূড়ান্ত লক্ষ্য পূরণ করতে কাজ করে।
</p>
<ul>
  <li><strong>State Awareness:</strong> কথোপকথনের শুরুতে "পাসপোর্ট" শব্দটি অস্পষ্ট (নতুন, নবায়ন, সংশোধন নাকি হারানো?)। এজেন্ট এটি বুঝে সরাসরি অনুমান না করে স্পষ্টীকরণ প্রশ্ন (Clarification Question) করে।</li>
  <li><strong>Slot Tracking:</strong> নির্দিষ্ট প্রশ্নের জন্য যা যা তথ্য দরকার (যেমন: পাসপোর্টের ফি জানতে হলে মেয়াদ ও ডেলিভারি মোড জানা আবশ্যক), এজেন্ট তা ট্র্যাক করে এবং অসম্পূর্ণ তথ্য থাকলে তা ইউজার থেকে জেনে নেয়।</li>
  <li><strong>Goal Fulfillment:</strong> যখন সমস্ত স্লট পূর্ণ হয়ে যায়, এজেন্ট তার লক্ষ্যে পৌঁছে যায় এবং ভেরিফায়েড ডাটাবেস থেকে নির্ভুল কার্ড তৈরি করে।</li>
</ul>

<h2>১.২ তিনটি অপরিহার্য মূলনীতি (The Three Core Design Rules)</h2>
<div class="box box-amber">
  <strong>১. তথ্য কখনো জেনারেট (Hallucinate) করা হয় না:</strong> সরকারি তথ্যে ১ টাকার বা ১ দিনের ভুলও নাগরিককে বড় ধরনের ভোগান্তিতে ফেলতে পারে। তাই ফি, মেয়াদ বা কাগজপত্রের তালিকা কখনোই এলএলএম (Gemini) কে দিয়ে লেখানো হয় না। উত্তর আসে সরাসরি যাচাইকৃত JSON ফাইল থেকে হুবহু উদ্ধৃত (Verbatim) করে। জেমিনি কেবল শুরুতে একটি মাত্র স্বাভাবিক সংযোগকারী বাক্য তৈরি করে।
</div>

<div class="box box-blue">
  <strong>২. কনফিডেন্স থ্রেশহোল্ডের নিচে রিফিউজাল (Refusal Guardrail):</strong> রিট্রিভাল স্কোরের মান <code>CONF_THRESHOLD</code> (০.৬২)-এর কম হলে সিস্টেম মনগড়া উত্তর না দিয়ে সরাসরি বলে যে তার কাছে এই বিষয়ে নিশ্চিত তথ্য নেই।
</div>

<div class="box box-green">
  <strong>৩. বাটন/চিপ ক্লিকে LLM সম্পূর্ণ বাইপাস (Fast Path ~৫ মিলি-সেকেন্ড):</strong> চিপ বা বাটনে চাপ দিলে ইউজারের ইনটেন্ট আগে থেকেই স্ট্রাকচার্ড থাকে। সেখানে এলএলএম ডাকার দরকার নেই; সরাসরি রিট্রিভাল থেকে নিমেষেই (০.০০৫ সেকেন্ডে) উত্তর চলে আসে।
</div>

<div class="page-break"></div>

<!-- Chapter 2 -->
<h1>অধ্যায় ২: সম্পূর্ণ সিস্টেম আর্কিটেকচার ও ডেটাফ্লো (Architecture & Flow)</h1>

<p>
  সিস্টেমটি দুটি প্রধান পাথে কাজ করে: একটি ফাস্ট পাথ (Chip Action) এবং অন্যটি ফুল পাথ (Free-text Chat)।
</p>

<pre><code>             [ ইউজার ব্রাউজার / UI (web/index.html) ]
                     │                      │
       (Chip Click)  │                      │  (Free-Text Bangla/English)
             ▼       │                      ▼
     POST /api/action                       POST /api/chat
             │                                      │
     (No Gemini Call)                       1. phrases.py (Deterministic Rules)
             │                              2. locations.py (64 District Office Check)
             │                              3. gemini-3.5-flash (Intent & Slot Understand)
             │                              4. Out of Scope / Refusal Guardrail
             │                                      │
             └───────────────► ◄────────────────────┘
                               │
                    [ Hybrid Retrieval Engine ]
                    - Cosine Similarity (data/embeddings.npz)
                    - Keyword Boosting (ফি, koto taka, GD)
                               │
                    [ Card Builder (agent.py) ]
                               │
                    [ JSON Response + UI Render ]
</code></pre>

<h2>২.১ ডুয়াল-পাথ মেকানিজম (Dual-Path Execution)</h2>
<table>
  <tr>
    <th>বৈশিষ্ট্য</th>
    <th>ফাস্ট পাথ (Fast Path) <span class="badge badge-fast">CHIP</span></th>
    <th>ফুল পাথ (Full Path) <span class="badge badge-llm">FREE TEXT</span></th>
  </tr>
  <tr>
    <td><strong>এন্ডপয়েন্ট</strong></td>
    <td><code>POST /api/action</code></td>
    <td><code>POST /api/chat</code></td>
  </tr>
  <tr>
    <td><strong>ইনপুট ধরন</strong></td>
    <td>বাটন/চিপ ক্লিক (Structured JSON)</td>
    <td>বাংলা, ইংরেজি বা বাংলিশ মুক্ত টেক্সট</td>
  </tr>
  <tr>
    <td><strong>Gemini API কল</strong></td>
    <td><strong>০ (কোনো কল হয় না)</strong></td>
    <td>১টি (ইনটেন্ট ও স্লট বোঝার জন্য)</td>
  </tr>
  <tr>
    <td><strong>রেসপন্স টাইম</strong></td>
    <td>~১ থেকে ৫ মিলি-সেকেন্ড (অতি দ্রুত)</td>
    <td>~১.২ থেকে ১.৮ সেকেন্ড (মডেলের উপর নির্ভরশীল)</td>
  </tr>
  <tr>
    <td><strong>রেট লিমিট প্রয়োগ</strong></td>
    <td>প্রযোজ্য নয় (আনলিমিটেড)</td>
    <td>প্রতি মিনিটে ৮টি, দিনে ৩০০টি (পার আইপি)</td>
  </tr>
</table>

<h2>২.২ হাইব্রিড রিট্রিভাল ইঞ্জিন (Hybrid Retrieval Engine)</h2>
<p>
  প্রজেক্টে রিট্রিভাল ইঞ্জিনে শুধু কসাইন সিমিলারিটি ব্যবহার করা হয়নি; সাথে কি-ওয়ার্ড বুস্টিং যুক্ত করা হয়েছে:
</p>
<ul>
  <li><strong>Cosine Similarity:</strong> <code>gemini-embedding-001</code> দিয়ে নলেজ বেইসের প্রতিটি এন্ট্রির ৩,০৭২ ডাইমেনশনের ভেক্টর তৈরি করা থাকে (<code>data/embeddings.npz</code>)। ইউজারের প্রশ্নের ভেক্টরের সাথে ম্যাট্রিক্স গুণন করে সাদৃশ্য পরিমাপ করা হয়।</li>
  <li><strong>Keyword Boosting:</strong> অনেক সময় এম্বেডিং "ফি", "koto taka", "GD", "মেয়াদ" ইত্যাদি নির্দিষ্ট ও গুরুত্বপূর্ণ শব্দ মিস করতে পারে। তাই <code>retriever.py</code>-তে কি-ওয়ার্ড মিললে স্কোরের সাথে অতিরিক্ত <code>+0.08</code> বুস্ট যোগ করা হয় (সর্বোচ্চ <code>+0.20</code> পর্যন্ত)।</li>
</ul>

<div class="page-break"></div>

<!-- Chapter 3 -->
<h1>অধ্যায় ৩: সম্পূর্ণ কোডবেস এবং ফাইল পরিচিতি (File-by-File Breakdown)</h1>

<p>
  প্রজেক্টের প্রতিটি ফাইল একটি সুনির্দিষ্ট দায়িত্ব পালন করে (Single Responsibility Principle):
</p>

<table>
  <tr>
    <th>ডিরেক্টরি ও ফাইল</th>
    <th>কাজের বিস্তারিত বিবরণ</th>
  </tr>
  <tr>
    <td><code>app/main.py</code></td>
    <td>FastAPI এর মূল অ্যাপ্লিকেশন ফাইল। সমস্ত REST API রাউট (<code>/api/chat</code>, <code>/api/action</code>, <code>/health</code>, <code>/api/meta</code>, <code>/api/admin/*</code>) এখানে ডিফাইন করা এবং <code>web/</code> ফোল্ডারের স্ট্যাটিক ফাইল পরিবেশন করে।</td>
  </tr>
  <tr>
    <td><code>app/agent.py</code></td>
    <td>গোল-বেসড এজেন্টের কেন্দ্রীয় মস্তিস্ক। এটি সিদ্ধান্ত নেয় কখন ইউজারকে পাল্টা প্রশ্ন করতে হবে (<code>_clarify</code>), কখন তথ্য নেই বলে ফিরিয়ে দিতে হবে (<code>_no_info</code>) এবং কখন কার্ড বানাতে হবে (<code>_answer</code>)।</td>
  </tr>
  <tr>
    <td><code>app/locations.py</code></td>
    <td><strong>(নতুন সংযোজিত ইঞ্জিন)</strong> বাংলাদেশের ৬৪টি জেলার পাসপোর্ট এবং বিআরটিএ অফিসের পূর্ণাঙ্গ ঠিকানা, সময়সূচী, হেল্পলাইন ও গুগল ম্যাপস ডাটা হ্যান্ডেল করে।</td>
  </tr>
  <tr>
    <td><code>app/phrases.py</code></td>
    <td>ডিটারমিনিস্টিক রুল ইঞ্জিন। বাংলা, ইংরেজি ও বাংলিশের শত শত সাধারণ বাক্যাংশের রেজেক্স (Regex) ম্যাচিং। এলএলএম ডাকার আগেই এটি ডোমেইন, সাবটাইপ ও স্লট নিখুঁতভাবে শনাক্ত করে।</td>
  </tr>
  <tr>
    <td><code>app/retriever.py</code></td>
    <td>নলেজ বেইসের উপর কসাইন স্ক্যান ও কি-ওয়ার্ড বুস্টিং চালায়। <code>embeddings.npz</code> ফাইল ক্যাশ করে রাখে যেন সার্ভার এক নিমেষে চালু হয়।</td>
  </tr>
  <tr>
    <td><code>app/llm.py</code></td>
    <td>গুগল জেমিনি (Google GenAI SDK) এর সাথে একমাত্র যোগাযোগের মাধ্যম। এখানে <code>gemini-3.5-flash</code> এবং <code>gemini-embedding-001</code> মডেল ব্যবহৃত হয় এবং সাময়িক ৫০৩ বা ৪২৯ এরর আসলে রিট্রাই (Retry Backoff) মেকানিজম আছে।</td>
  </tr>
  <tr>
    <td><code>app/kb.py</code></td>
    <td>নলেজ বেইস ট্যাক্সোনমি (১৪টি সাবটাইপ, ৫টি স্লট) সংজ্ঞায়িত করে এবং JSON ফাইলগুলো ভ্যালিডেট করে লোড করে।</td>
  </tr>
  <tr>
    <td><code>app/session.py</code></td>
    <td>ইন-মেমোরি সেশন ম্যানেজার। প্রতিটি ইউজারের কনভারসেশন স্টেট, স্লট ভ্যালু এবং প্রিভিয়াস হিস্ট্রি ১ ঘণ্টার জন্য মেমোরিতে রাখে।</td>
  </tr>
  <tr>
    <td><code>app/limits.py</code></td>
    <td>ক্লায়েন্টের আইপি অ্যাড্রেসের ওপর ভিত্তি করে ইন-মেমোরি রেট লিমিটার (Rate Limiting)।</td>
  </tr>
  <tr>
    <td><code>app/analytics.py</code></td>
    <td>SQLite ডাটাবেস (<code>data/analytics.db</code>) ব্যবহার করে প্রতিটি প্রশ্ন, ইউজারের লাইক/ডিসলাইক ফিডব্যাক এবং টপ প্রবলেম স্ট্যাটস সংরক্ষণ করে।</td>
  </tr>
  <tr>
    <td><code>data/passport.json</code></td>
    <td>পাসপোর্টের নতুন আবেদন, রি-ইস্যু, সংশোধন, হারানো, ডেলিভারি স্লিপ ইত্যাদি যাচাইকৃত তথ্যের ডাটাবেস।</td>
  </tr>
  <tr>
    <td><code>data/licence.json</code></td>
    <td>ড্রাইভিং লাইসেন্সের লার্নার, স্মার্টকার্ড, নবায়ন, হারিয়ে যাওয়া, পরীক্ষা ইত্যাদির তথ্যাবলী।</td>
  </tr>
  <tr>
    <td><code>data/offices.json</code></td>
    <td>বাংলাদেশের ৬৪ জেলার পাসপোর্ট ও বিআরটিএ অফিসের নাম, ঠিকানা, অফিস সময় ও ফোন নম্বর সম্বলিত ডাটাবেস।</td>
  </tr>
  <tr>
    <td><code>web/index.html</code></td>
    <td>সম্পূর্ণ ক্লায়েন্ট-সাইড সিঙ্গেল পেজ অ্যাপ্লিকেশন (SPA)। আধুনিক গ্লাস-মরফিজম কনসোল, চ্যাট হিস্ট্রি, শব্দ ধরে ধরে প্রোগ্রেসিভ স্ট্রিমিং ও ডার্ক/লাইট মোড সমর্থন করে।</td>
  </tr>
  <tr>
    <td><code>eval/run_eval.py</code></td>
    <td>৪০টি প্রমিত টেস্ট কুয়েরির উপর এজেন্টের সক্ষমতা মাপার অটোমেটেড ইভালুয়েশন স্ক্রিপ্ট।</td>
  </tr>
</table>

<div class="page-break"></div>

<!-- Chapter 4 -->
<h1>অধ্যায় ৪: নতুন ফিচার: ৬৪ জেলা অফিস লুকআপ ইঞ্জিন</h1>

<p>
  নাগরিকদের বহুল জিজ্ঞাসিত প্রশ্ন: <em>"রংপুরে পাসপোর্ট অফিস কোথায়?"</em> বা <em>"বগুড়ায় বিআরটিএ অফিস কোথায়?"</em> এর মতো প্রশ্নের জন্য প্রজেক্টে একটি নিবেদিত <strong>Location Lookup Engine</strong> যোগ করা হয়েছে।
</p>

<h2>৪.১ ডেটা স্ট্রাকচার ও ম্যাপিং</h2>
<p>
  ৬৪ জেলার তথ্য <code>data/offices.json</code> ফাইলে সংরক্ষিত। উদাহরণস্বরূপ রংপুর জেলার তথ্য:
</p>
<pre><code>{
  "rangpur": {
    "name_bn": "রংপুর",
    "aliases": ["রংপুর", "রংপুরে", "রংপুরের", "rangpur", "rongpur"],
    "passport": {
      "office_name_bn": "আঞ্চলিক পাসপোর্ট অফিস, রংপুর",
      "address_bn": "কেরানীপাড়া (চিড়িয়াখানার বিপরীতে), রংপুর সদর, রংপুর।",
      "hours_bn": "রবিবার - বৃহস্পতিবার, সকাল ৯:০০ - বিকাল ৪:০০",
      "phone_bn": "০২৫৮৯৯৬২২২২"
    },
    "licence": {
      "office_name_bn": "বিআরটিএ রংপুর সার্কেল অফিস",
      "address_bn": "কালেক্টরেট ভবন কম্পাউন্ড, রংপুর।",
      "hours_bn": "রবিবার - বৃহস্পতিবার, সকাল ৯:০০ - বিকাল ৪:০০",
      "phone_bn": "০৫২১-৬২৩৪৫"
    }
  }
}
</code></pre>

<h2>৪.২ এক্সিকিউশন ও আউটপুট ফরম্যাট</h2>
<p>
  ইউজার যখন মেসেজে জেলা এবং অফিস জানতে চায় (যেমন: <code>"রংপুরে পাসপোর্ট অফিস কোথায়?"</code>), <code>locations.py</code> সরাসরি ০.০১ সেকেন্ডের মধ্যে টেক্সট রেসপন্স তৈরি করে দেয়:
</p>

<div class="box box-green">
  <strong>আঞ্চলিক পাসপোর্ট অফিস, রংপুর</strong><br>
  📍 <strong>ঠিকানা:</strong> কেরানীপাড়া (চিড়িয়াখানার বিপরীতে), রংপুর সদর, রংপুর।<br>
  ⏰ <strong>অফিসের সময়সূচী:</strong> রবিবার - বৃহস্পতিবার, সকাল ৯:০০ - বিকাল ৪:০০<br>
  📞 <strong>হেল্পলাইন:</strong> ০২৫৮৯৯৬২২২২
</div>

<p>
  আর যদি ইউজার জেলা উল্লেখ না করে কেবল <em>"অফিস কোথায়?"</em> লিখে, তবে বট তাৎক্ষণিক চিপস সহ পাল্টা প্রশ্ন করে:
</p>
<div class="box box-blue">
  <em>"আপনি কোন জেলার অফিসের ঠিকানা জানতে চাচ্ছেন? নিচের তালিকা থেকে নির্বাচন করুন অথবা জেলার নাম লিখুন:"</em><br>
  চিপস: <code>[রংপুর]</code> <code>[ঢাকা]</code> <code>[চট্টগ্রাম]</code> <code>[রাজশাহী]</code> <code>[সিলেট]</code> <code>[খুলনা]</code> <code>[বরিশাল]</code> <code>[বগুড়া]</code>
</div>

<div class="page-break"></div>

<!-- Chapter 5 -->
<h1>অধ্যায় ৫: জিরো থেকে প্রজেক্ট তৈরি ও রান করার গাইড (Step-by-Step Setup)</h1>

<p>
  যেকোনো ফ্রেশ কম্পিউটারে এই প্রজেক্টটি স্ক্র্যাচ বা জিরো থেকে রান করার জন্য নিচের ধাপগুলো অনুসরণ করতে হয়:
</p>

<h3>ধাপ ১: পাইথন ও ডিপেনডেন্সি প্রস্তুতকরণ</h3>
<pre><code># ১. প্রজেক্ট ডিরেক্টরিতে যান
cd "E:\\BAUST\\LEVEL 3 TERM II\\AI Sessional\\AI-Based-Government-Service-Guide-for-Bangladesh-Developer"

# ২. ডিপেনডেন্সিগুলো ইন্সটল করুন
pip install fastapi uvicorn[standard] pydantic python-dotenv numpy google-genai
</code></pre>

<h3>ধাপ ২: এনভায়রনমেন্ট কনফিগারেশন (.env)</h3>
<p>
  প্রজেক্টের রুটে <code>.env</code> ফাইল তৈরি করে API কী এবং সক্রিয় মডেল নির্ধারণ করা হয়:
</p>
<pre><code># .env
GEMINI_API_KEY=your_gemini_api_key_here
CHAT_MODEL=gemini-3.5-flash
EMBED_MODEL=gemini-embedding-001
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
CONF_THRESHOLD=0.62
RATE_PER_MIN=8
RATE_PER_DAY=300
ALLOWED_ORIGINS=*
</code></pre>

<h3>ধাপ ৩: সার্চ ইনডেক্স তৈরি (Embeddings Build)</h3>
<pre><code># এটি প্রথমবার চালানোর পর data/embeddings.npz ফাইল তৈরি হবে
python -m app.index
</code></pre>

<h3>ধাপ ৪: সিস্টেম ডায়াগনস্টিক টেস্ট (Health Check)</h3>
<pre><code>python check.py
# এটি কী লোড, জেমিনি কানেকশন, JSON মোড এবং রিট্রিভালের ৬টি টেস্ট স্বয়ংক্রিয়ভাবে যাচাই করে
</code></pre>

<h3>ধাপ ৫: সার্ভার চালু করা</h3>
<pre><code>python -m uvicorn app.main:app --reload --port 8000
</code></pre>
<p>
  এখন যেকোনো ব্রাউজারে <code>http://127.0.0.1:8000</code> ওপেন করলেই সেবা সহায়ক লাইভ ব্যবহার করা যাবে!
</p>

<div class="page-break"></div>

<!-- Chapter 6 -->
<h1>অধ্যায় ৬: ভাইভা ও প্রেজেন্টেশনের সম্ভাব্য প্রশ্নোত্তর (Viva Q&A Cheat Sheet)</h1>

<div class="box box-green">
  <strong>প্রশ্ন ১: এই প্রজেক্টে জেমিনি (LLM) দিয়ে সরাসরি উত্তর জেনারেট না করিয়ে RAG থেকে Verbatim টেক্সট কেন দেখাচ্ছেন?</strong><br>
  <strong>উত্তর:</strong> সরকারি সেবার ক্ষেত্রে "Hallucination" বা ভুল তথ্য তৈরি সম্পূর্ণ অগ্রহণযোগ্য। এলএলএম যদি সরকারি ফি ৩,৪৫০ টাকার জায়গায় ভুল করে ৪,০৫০ টাকা বলে ফেলে, তবে নাগরিক ব্যাংকে গিয়ে বিভ্রান্ত হবে। তাই আমাদের নীতি: <em>Facts are never generated.</em> যাচাইকৃত তথ্য ডাটাবেস থেকে হুবহু দেখানো হয়, আর জেমিনি শুধু শুরুতে একটি সাবলীল সংযোগকারী বাক্য লিখে দেয়।
</div>

<div class="box box-blue">
  <strong>প্রশ্ন ২: ভেক্টর ডাটাবেস হিসেবে Pinecone, ChromaDB বা FAISS ব্যবহার করেননি কেন?</strong><br>
  <strong>উত্তর:</strong> আমাদের নলেজ বেইসে প্রায় ৭০টি ভেরিফায়েড এন্ট্রি রয়েছে। ৭০টি এন্ট্রির ৩,০৭২ ডাইমেনশনের ভেক্টর ম্যাট্রিক্স কসাইন স্ক্যান করতে NumPy-তে মাত্র ০.০০১ সেকেন্ড (১ মিলি-সেকেন্ড) লাগে! এখানে Chroma বা Pinecone ব্যবহার করলে সিস্টেমের কোল্ড-স্টার্ট ধীর হতো এবং অপ্রয়োজনীয় থার্ড-পার্টি ডিপেনডেন্সি বাড়ত।
</div>

<div class="box box-green">
  <strong>প্রশ্ন ৩: গোল-বেসড এজেন্টের সিদ্ধান্ত গ্রহণ প্রক্রিয়াটি কীভাবে কাজ করে?</strong><br>
  <strong>উত্তর:</strong> ইউজারের একটি নির্দিষ্ট লক্ষ্য পূরণ না হওয়া পর্যন্ত এজেন্ট তাকে স্পষ্টীকরণ প্রশ্ন করে। উদাহরণস্বরূপ: কেউ যদি বলে "পাসপোর্টের ফি কত?", কিন্তু মেয়াদ (৫ বছর না ১০ বছর?) এবং ডেলিভারি টাইপ (রেগুলার না এক্সপ্রেস?) না বলে, তবে এজেন্ট রিট্রিভালে না গিয়ে সরাসরি মিসিং স্লটটি পূরণ করার জন্য প্রশ্ন ও চিপস পাঠায়। স্লট পূরণ হলেই সে কার্ড তৈরি করে।
</div>

<div class="box box-amber">
  <strong>প্রশ্ন ৪: ফ্রি-টিয়ার এপিআই কোটা ও রেট লিমিট কীভাবে ম্যানেজ করছেন?</strong><br>
  <strong>উত্তর:</strong> তিনটি কৌশলে:
  ১. চিপ বা বাটনে ক্লিক করলে কোনো জেমিনি কল হয় না (০ এপিআই খরচ)।
  ২. সালাম, ধন্যবাদ ও পরিচিতিমূলক সাধারণ মেসেজগুলো (Smalltalk) রেজেক্স দিয়ে ধরা হয়, যাতে কোটা খরচ না হয়।
  ৩. <code>limits.py</code>-এর মাধ্যমে প্রতি আইপিতে মিনিটে ৮টি ও দিনে ৩০০টি কুয়েরির ট্রাফিক লিমিট কার্যকর রাখা হয়েছে।
</div>

<div class="box box-blue">
  <strong>প্রশ্ন ৫: প্রজেক্টের সঠিকতা (Accuracy) কীভাবে পরিমাপ করেছেন?</strong><br>
  <strong>উত্তর:</strong> <code>eval/testset.json</code> ফাইলে ৪০টি প্রমিত প্রশ্ন রয়েছে (পরিষ্কার বাংলা, ইংরেজি, বাংলিশ, অস্পষ্ট বাক্য, ফলো-আপ ও আউট-অফ-স্কোপ)। <code>python -m eval.run_eval</code> দিয়ে টেস্ট চালালে দেখা যায় প্রজেক্টটি ৯৫%+ সঠিকতায় সাব-টাইপ ও ইনটেন্ট নির্ণয় করতে সক্ষম।
</div>

</body>
</html>
"""

html_path = Path("PROJECT_MASTER_GUIDE.html")
html_path.write_text(html_content, encoding="utf-8")
print(f"Generated HTML guide at {html_path.resolve()}")

pdf_path = Path("SEBA_SOHAYOK_COMPLETE_PROJECT_GUIDE.pdf")
edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

browser_path = edge_path if os.path.exists(edge_path) else chrome_path

cmd = [
    "powershell", "-Command",
    f"Start-Process -FilePath '{browser_path}' -ArgumentList '--headless', '--disable-gpu', '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw', '--print-to-pdf=\"{pdf_path.resolve()}\"', '\"{html_path.resolve()}\"' -Wait"
]

print("Converting HTML to PDF via browser engine...")
subprocess.run(cmd, check=True)

if pdf_path.exists():
    size_kb = pdf_path.stat().st_size / 1024
    print(f"SUCCESS! Created PDF at {pdf_path.resolve()} ({size_kb:.1f} KB)")
else:
    print("PDF generation failed.")
