"""SecureShip sample API.

Deliberately small: the security pipeline around it is the product.
Interactive docs and the OpenAPI schema are disabled to reduce exposed surface.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

APP_VERSION = "1.0.0"

app = FastAPI(
    title="SecureShip Demo API",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

HOME_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#090d18">
  <title>SecureShip | Ship securely</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090d18;
      --panel: rgba(18, 25, 43, .82);
      --line: rgba(165, 184, 218, .14);
      --muted: #9aa8c2;
      --text: #f3f6ff;
      --mint: #78f0c2;
      --blue: #83a9ff;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-width: 320px;
      color: var(--text);
      background:
        radial-gradient(ellipse at 82% 4%, rgba(80, 107, 227, .18), transparent 35rem),
        radial-gradient(ellipse at 5% 34%, rgba(45, 205, 157, .08), transparent 30rem),
        var(--bg);
      font: 16px/1.6 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: inherit; }
    .wrap { width: min(1120px, calc(100% - 48px)); margin: 0 auto; }
    header {
      height: 82px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; align-items: center; gap: 12px; font-size: 19px; font-weight: 750; letter-spacing: -.04em; }
    .brand-mark {
      width: 36px; height: 36px; display: grid; place-items: center;
      border: 1px solid rgba(120, 240, 194, .35); border-radius: 11px;
      color: var(--mint); background: rgba(120, 240, 194, .1);
    }
    .brand-mark svg { width: 21px; height: 21px; }
    .nav-note { color: var(--muted); font-size: 13px; letter-spacing: .08em; text-transform: uppercase; }
    main { padding: 72px 0 84px; }
    .hero { display: grid; grid-template-columns: 1.08fr .92fr; gap: 54px; align-items: center; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: 9px; color: var(--mint);
      font-size: 12px; font-weight: 750; letter-spacing: .14em; text-transform: uppercase;
    }
    .pulse { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 14px var(--mint); }
    h1 { margin: 20px 0 18px; font-size: clamp(46px, 6vw, 72px); line-height: 1.02; letter-spacing: -.065em; }
    h1 span { color: var(--mint); }
    .intro { max-width: 560px; margin: 0; color: #b1bdd2; font-size: 18px; line-height: 1.75; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 30px; }
    .button {
      display: inline-flex; min-height: 46px; align-items: center; justify-content: center;
      padding: 0 18px; border: 1px solid var(--line); border-radius: 10px;
      text-decoration: none; font-size: 14px; font-weight: 700; transition: transform .18s ease, border-color .18s ease;
    }
    .button:hover { transform: translateY(-2px); border-color: rgba(120, 240, 194, .65); }
    .button.primary { color: #07130f; border-color: var(--mint); background: var(--mint); }
    .button.secondary { color: #dce5f6; background: rgba(255,255,255,.025); }
    .note { margin-top: 18px; color: #8492aa; font-size: 12px; }
    .visual {
      position: relative; padding: 24px; border: 1px solid rgba(157, 177, 214, .18);
      border-radius: 20px; background: linear-gradient(145deg, rgba(24, 34, 57, .92), rgba(13, 19, 33, .92));
      box-shadow: 0 28px 90px rgba(0,0,0,.32);
    }
    .visual::before { position: absolute; inset: -1px; z-index: -1; border-radius: 21px; content: ""; background: linear-gradient(135deg, rgba(120,240,194,.28), transparent 45%, rgba(131,169,255,.25)); filter: blur(18px); }
    .visual-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .visual-title { font-size: 14px; font-weight: 720; }
    .live-label { color: #b8c5dc; font-size: 11px; }
    .live-label::before { display: inline-block; width: 6px; height: 6px; margin: 0 7px 1px 0; border-radius: 50%; background: var(--blue); content: ""; }
    .flow { display: grid; gap: 10px; }
    .flow-item {
      display: grid; grid-template-columns: 38px 1fr auto; gap: 12px; align-items: center;
      padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: rgba(7, 12, 23, .42);
    }
    .flow-icon { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 10px; color: var(--blue); background: rgba(131,169,255,.1); font-size: 13px; font-weight: 800; }
    .flow-item:nth-child(2) .flow-icon, .flow-item:nth-child(4) .flow-icon { color: var(--mint); background: rgba(120,240,194,.1); }
    .flow-name { font-size: 13px; font-weight: 700; }
    .flow-desc { color: #8998b2; font-size: 11px; }
    .flow-status { color: #a7b5ca; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }
    .flow-status.gate { color: var(--mint); }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
    .metric { padding: 12px 10px; border: 1px solid var(--line); border-radius: 11px; text-align: center; background: rgba(7,12,23,.3); }
    .metric strong { display: block; color: var(--text); font-size: 18px; letter-spacing: -.04em; }
    .metric span { color: #8998b2; font-size: 10px; }
    section { margin-top: 86px; }
    .section-kicker { color: var(--blue); font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
    h2 { margin: 9px 0 12px; font-size: clamp(28px, 4vw, 40px); line-height: 1.15; letter-spacing: -.045em; }
    .section-copy { max-width: 670px; margin: 0; color: var(--muted); }
    .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 28px; }
    .card { min-height: 176px; padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel); }
    .card-tag { color: var(--mint); font-size: 11px; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }
    .card h3 { margin: 12px 0 7px; font-size: 17px; letter-spacing: -.025em; }
    .card p { margin: 0; color: var(--muted); font-size: 13px; }
    .deploy-band {
      display: flex; justify-content: space-between; align-items: center; gap: 24px;
      margin-top: 64px; padding: 24px 27px; border: 1px solid rgba(120,240,194,.2);
      border-radius: 16px; background: linear-gradient(110deg, rgba(120,240,194,.08), rgba(131,169,255,.06));
    }
    .deploy-band h2 { margin: 0 0 5px; font-size: 21px; }
    .deploy-band p { margin: 0; color: var(--muted); font-size: 13px; }
    footer { display: flex; justify-content: space-between; gap: 20px; padding: 22px 0 30px; border-top: 1px solid var(--line); color: #7f8da5; font-size: 12px; }
    footer a { color: #a8b8d2; text-decoration: none; }
    footer a:hover { color: var(--mint); }
    @media (max-width: 850px) {
      main { padding-top: 50px; }
      .hero { grid-template-columns: 1fr; gap: 38px; }
      .cards { grid-template-columns: repeat(2, 1fr); }
      section { margin-top: 64px; }
    }
    @media (max-width: 520px) {
      .wrap { width: min(100% - 32px, 1120px); }
      header { height: 68px; }
      .nav-note { font-size: 10px; }
      main { padding-top: 42px; }
      .intro { font-size: 16px; }
      .visual { padding: 16px; }
      .flow-item { grid-template-columns: 34px 1fr; }
      .flow-status { grid-column: 2; }
      .cards { grid-template-columns: 1fr; }
      .deploy-band { align-items: flex-start; flex-direction: column; }
      footer { flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <a class="brand" href="/" aria-label="SecureShip home">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none"><path d="M12 3 19 6v5c0 4.7-2.8 8-7 10-4.2-2-7-5.3-7-10V6l7-3Z" stroke="currentColor" stroke-width="1.7"/><path d="m9 12 2 2 4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        SecureShip
      </a>
      <span class="nav-note">Security-first delivery</span>
    </header>

    <main>
      <div class="hero">
        <div>
          <div class="eyebrow"><span class="pulse" aria-hidden="true"></span> A safer path from commit to cloud</div>
          <h1>Ship fast.<br><span>Ship securely.</span></h1>
          <p class="intro">SecureShip demonstrates how security checks can become part of everyday delivery: test the app, scan the code and infrastructure, then let policy decide whether an image can reach AWS.</p>
          <div class="actions">
            <a class="button primary" href="#pipeline">Explore the pipeline <span aria-hidden="true">&nbsp;↓</span></a>
            <a class="button secondary" href="/health">Check API health <span aria-hidden="true">&nbsp;↗</span></a>
          </div>
          <p class="note">This page explains the sample project; it does not display live scan or deployment status.</p>
        </div>

        <aside class="visual" aria-label="Illustration of the SecureShip delivery pipeline">
          <div class="visual-head">
            <span class="visual-title">The delivery path</span>
            <span class="live-label">Pipeline overview</span>
          </div>
          <div class="flow">
            <div class="flow-item"><span class="flow-icon">01</span><span><span class="flow-name">Code &amp; tests</span><br><span class="flow-desc">FastAPI · pytest</span></span><span class="flow-status">Verify</span></div>
            <div class="flow-item"><span class="flow-icon">02</span><span><span class="flow-name">Security scans</span><br><span class="flow-desc">Gitleaks · Trivy · Checkov</span></span><span class="flow-status">Inspect</span></div>
            <div class="flow-item"><span class="flow-icon">03</span><span><span class="flow-name">Policy decision</span><br><span class="flow-desc">Findings are evaluated together</span></span><span class="flow-status gate">Pass / block</span></div>
            <div class="flow-item"><span class="flow-icon">04</span><span><span class="flow-name">Approved release</span><br><span class="flow-desc">ECR image digest → EC2</span></span><span class="flow-status">Deploy</span></div>
          </div>
          <div class="metrics">
            <div class="metric"><strong>3</strong><span>scanner tools</span></div>
            <div class="metric"><strong>1</strong><span>policy gate</span></div>
            <div class="metric"><strong>0</strong><span>stored AWS keys</span></div>
          </div>
        </aside>
      </div>

      <section id="pipeline">
        <span class="section-kicker">What we are doing</span>
        <h2>Security checks before deployment.</h2>
        <p class="section-copy">Every pull request is tested and scanned. The policy engine blocks configured violations. Only a passing build on the main branch is published and deployed, using short-lived AWS credentials through GitHub OIDC.</p>
        <div class="cards">
          <article class="card"><span class="card-tag">01 / Secrets</span><h3>Gitleaks</h3><p>Looks for exposed credentials in the repository history. Findings are redacted before they are reported.</p></article>
          <article class="card"><span class="card-tag">02 / Vulnerabilities</span><h3>Trivy</h3><p>Checks Python dependencies and the built container image for known vulnerabilities.</p></article>
          <article class="card"><span class="card-tag">03 / Infrastructure</span><h3>Checkov</h3><p>Reviews Terraform configuration for cloud security misconfigurations before it is applied.</p></article>
          <article class="card"><span class="card-tag">04 / Decision</span><h3>Python policy engine</h3><p>Combines scan results into one pass-or-block decision. Missing scan reports fail closed.</p></article>
        </div>
        <div class="deploy-band">
          <div><h2>From approved image to AWS.</h2><p>GitHub Actions pushes the scanned image to ECR, then deploys its immutable digest to EC2 through Systems Manager.</p></div>
          <a class="button secondary" href="/version">View build version <span aria-hidden="true">&nbsp;↗</span></a>
        </div>
      </section>
    </main>

    <footer>
      <span>SecureShip · A compact DevSecOps learning project</span>
      <span>FastAPI <span aria-hidden="true">·</span> Docker <span aria-hidden="true">·</span> GitHub Actions <span aria-hidden="true">·</span> AWS</span>
    </footer>
  </div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(HOME_PAGE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": APP_VERSION, "git_sha": os.getenv("GIT_SHA", "unknown")}


@app.get("/api/greet")
def greet(
    name: str = Query(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9 _.-]+$",
        description="Letters, digits, space, dot, dash and underscore only.",
    ),
) -> dict[str, str]:
    """Input is validated with an allow-list pattern, not sanitised afterwards."""
    return {"message": f"Hello, {name.strip()}!"}
