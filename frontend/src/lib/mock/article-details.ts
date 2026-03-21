import type { ArticleDetail, ArticleListItem } from "@/types/articles";

export const mockArticleDetails: ArticleDetail[] = [
  {
    id: "art-001",
    title: "AI-Powered Phishing Detection Trends",
    subtitle: "How machine learning is reshaping email security in 2026",
    bodyMarkdown: `## The Evolving Phishing Landscape

Phishing attacks have grown more sophisticated in 2026, with threat actors leveraging large language models to craft convincing lures that bypass traditional rule-based filters. Security researchers at Proofpoint documented a 340% increase in AI-assisted spear phishing campaigns over the previous year [1]. These attacks use publicly available LLMs to generate personalized email content that mimics legitimate correspondence with near-perfect grammar and contextually accurate details.

Traditional signature-based detection, which relies on known malicious URLs and sender patterns, fails against polymorphic phishing kits that rotate infrastructure on hourly cycles [2]. The result is a detection gap that leaves organizations exposed for hours before defenders update blocklists. Mean time to detection for novel phishing campaigns now sits at 4.2 hours according to the 2026 Verizon Data Breach Investigations Report [3].

## How AI Detection Systems Work

Modern AI-powered detection platforms apply transformer-based classifiers trained on millions of labeled email samples. Rather than matching patterns, these models learn the semantic features that distinguish legitimate business communication from manipulation attempts. Key signals include urgency framing, unusual sender-recipient relationship graphs, anomalous link structures, and deviations from an organization's baseline communication style [4].

Google's anti-phishing team published results showing that their BERT-derived email classifier reduces false negatives by 63% compared to the prior generation of heuristic filters, with a false positive rate below 0.1% [5]. The model processes each incoming message in under 12 milliseconds, making it viable for real-time gateway deployment without introducing noticeable latency.

Behavioral baselines are particularly effective against business email compromise (BEC). By modeling the historical patterns of each executive and finance team member, anomaly detection surfaces requests that deviate from established norms—wire transfer instructions sent from a mobile device at 11 PM, or invoice approvals routed through an unfamiliar IP [1].

## Deployment Challenges and What Comes Next

Deploying AI detection at scale introduces its own complexity. Security teams must manage model drift as attacker tactics evolve, balance sensitivity thresholds to limit alert fatigue, and maintain interpretability so analysts can understand why a message was flagged [6]. Explainability remains an open problem: transformer attention weights provide some signal but rarely surface a clear human-readable rationale.

The near-term outlook favors a layered approach: AI classifiers at the gateway, graph-based anomaly detection for lateral movement inside the inbox, and user-facing nudges that present real-time risk scores at the moment of a click. Organizations piloting this stack have reported a 71% reduction in credentials submitted to phishing pages within the first quarter of deployment [3].

## References

1. Proofpoint Threat Research Team — "State of the Phish 2026"
2. Mandiant Threat Intelligence — "Polymorphic Phishing Kit Analysis Q1 2026"
3. Verizon DBIR 2026
4. Microsoft Security Blog — "Semantic Email Classification at Scale"
5. Google Security Blog — "BERT-Based Anti-Phishing at Gmail"
6. SANS Institute — "AI in SOC Operations: Pitfalls and Patterns"
`,
    summary:
      "AI-powered phishing detection is reducing detection gaps from hours to milliseconds by applying transformer-based classifiers that analyze semantic features and behavioral baselines rather than static signatures.",
    keyClaims: [
      "AI-assisted spear phishing campaigns increased 340% year-over-year according to Proofpoint research.",
      "Traditional signature-based detection fails against polymorphic phishing kits that rotate infrastructure hourly.",
      "BERT-derived email classifiers reduce false negatives by 63% with a false positive rate below 0.1%.",
      "Organizations deploying layered AI detection report a 71% reduction in credentials submitted to phishing pages.",
      "Mean time to detection for novel phishing campaigns is 4.2 hours without AI-assisted tooling.",
    ],
    contentType: "article",
    seo: {
      title: "AI-Powered Phishing Detection Trends 2026 | Cognify",
      description:
        "How machine learning and transformer-based classifiers are closing the detection gap on AI-crafted phishing attacks in 2026.",
      keywords: [
        "phishing detection",
        "AI email security",
        "machine learning cybersecurity",
        "BEC detection",
        "transformer classifier",
      ],
      canonicalUrl: null,
      structuredData: null,
    },
    citations: [
      {
        index: 1,
        title: "State of the Phish 2026",
        url: "https://www.proofpoint.com/us/resources/threat-reports/state-of-phish",
        authors: ["Proofpoint Threat Research Team"],
        publishedAt: "2026-02-14T00:00:00Z",
      },
      {
        index: 2,
        title: "Polymorphic Phishing Kit Analysis Q1 2026",
        url: "https://www.mandiant.com/resources/blog/polymorphic-phishing-2026",
        authors: ["Mandiant Threat Intelligence"],
        publishedAt: "2026-01-28T00:00:00Z",
      },
      {
        index: 3,
        title: "2026 Data Breach Investigations Report",
        url: "https://www.verizon.com/business/resources/reports/dbir/",
        authors: ["Verizon Security Research"],
        publishedAt: "2026-03-01T00:00:00Z",
      },
      {
        index: 4,
        title: "Semantic Email Classification at Scale",
        url: "https://www.microsoft.com/en-us/security/blog/semantic-email-classification",
        authors: ["Microsoft Security Team"],
        publishedAt: "2026-01-15T00:00:00Z",
      },
      {
        index: 5,
        title: "BERT-Based Anti-Phishing at Gmail",
        url: "https://security.googleblog.com/bert-anti-phishing-gmail-2026",
        authors: ["Google Security Team"],
        publishedAt: "2026-02-03T00:00:00Z",
      },
      {
        index: 6,
        title: "AI in SOC Operations: Pitfalls and Patterns",
        url: "https://www.sans.org/white-papers/ai-soc-operations-2026",
        authors: ["SANS Institute"],
        publishedAt: "2026-01-20T00:00:00Z",
      },
    ],
    visuals: [],
    authors: ["Cognify AI"],
    domain: "cybersecurity",
    generatedAt: "2026-03-21T08:00:00Z",
    provenance: {
      researchSessionId: "rsess-a001",
      primaryModel: "claude-opus-4",
      draftingModel: "claude-sonnet-4",
      embeddingModel: "all-MiniLM-L6-v2",
      embeddingVersion: "v2.0",
    },
    aiGenerated: true,
    status: "complete",
    wordCount: 0, // computed below
    workflow: [
      { name: "Research", durationSeconds: 187 },
      { name: "Outline", durationSeconds: 14 },
      { name: "Drafting", durationSeconds: 63 },
      { name: "Humanization", durationSeconds: 21 },
      { name: "SEO", durationSeconds: 18 },
      { name: "Finalized", durationSeconds: 4 },
    ],
  },
  {
    id: "art-002",
    title: "Zero Trust Architecture in 2026",
    subtitle: "From principle to production — what enterprise deployments look like today",
    bodyMarkdown: `## Why Perimeter Security Is Insufficient

The implicit trust model that once secured corporate networks was built around a clear boundary: inside the firewall meant safe, outside meant hostile. That boundary dissolved with the mass adoption of cloud workloads, remote work, and SaaS applications. By 2026, the average enterprise routes 73% of its application traffic through public cloud or CDN infrastructure, making the traditional perimeter largely a fiction [1].

Zero Trust replaces implicit trust with continuous verification. Every request—regardless of origin—is treated as potentially hostile until identity, device posture, and context are validated against policy. NIST SP 800-207 defines the five pillars: identity, device, network, application workload, and data [2]. Mature implementations instrument each pillar independently, which means a compromised credential alone is insufficient to access sensitive resources if the associated device fails a posture check.

## What Enterprise Deployments Actually Look Like

Gartner reports that 63% of enterprises have a Zero Trust initiative underway, but only 10% have reached what the firm categorizes as "advanced" maturity [3]. The gap is telling: most organizations have deployed identity-centric controls—multi-factor authentication, conditional access—but have not tackled the harder problems of microsegmentation and workload identity.

Microsegmentation divides the network into small zones, each with its own access policy, so that a breach in one segment cannot spread laterally. Illumio's 2026 survey found that organizations with mature microsegmentation contained breaches to a median of 1.3 systems, compared to 17.8 for organizations relying on flat network architecture [4]. The catch is operational burden: policy authoring and maintenance require tight integration between security teams and application owners, a collaboration that many organizations have not yet institutionalized.

Service mesh technology has emerged as the practical path to workload identity at scale. By injecting a sidecar proxy into each container, platforms like Istio issue short-lived mTLS certificates that encode workload identity. Communication between services is then encrypted and authenticated without requiring application code changes [5]. Combined with SPIFFE/SPIRE for identity attestation, this pattern makes it possible to enforce Zero Trust policies across thousands of microservices.

## Measuring Progress and the Road Ahead

Quantifying Zero Trust maturity is difficult because the framework spans organizational, process, and technical domains. CISA's Zero Trust Maturity Model provides a structured self-assessment tool across its five pillars, with each scored on a four-level scale from Traditional to Optimal [6]. The model gives security leaders a common vocabulary for communicating progress to executives and board members.

The most consequential near-term development is the convergence of SASE (Secure Access Service Edge) and Zero Trust Network Access (ZTNA). As SASE platforms mature, they offer an integrated stack—identity-aware proxy, cloud firewall, DLP, and CASB—delivered from the edge. For mid-market organizations that lack the engineering capacity to compose their own stack, SASE represents the most practical on-ramp to Zero Trust at reasonable operational cost.

## References

1. Gartner Research — "Cloud Adoption and Network Architecture 2026"
2. NIST SP 800-207 Zero Trust Architecture
3. Gartner Magic Quadrant for Zero Trust Network Access 2026
4. Illumio Zero Trust Impact Report 2026
5. CNCF — "Service Mesh Landscape 2026"
6. CISA Zero Trust Maturity Model v2.0
`,
    summary:
      "Enterprise Zero Trust adoption is accelerating but most organizations remain stuck at identity controls; microsegmentation and workload identity via service mesh represent the next maturity frontier.",
    keyClaims: [
      "73% of enterprise application traffic routes through public cloud or CDN, making perimeter security insufficient.",
      "Only 10% of enterprises with a Zero Trust initiative have reached advanced maturity per Gartner.",
      "Mature microsegmentation contains breaches to a median of 1.3 systems versus 17.8 in flat networks.",
      "Service mesh with mTLS and SPIFFE/SPIRE enables workload identity across thousands of microservices without code changes.",
      "CISA's Zero Trust Maturity Model provides a four-level self-assessment framework across five security pillars.",
    ],
    contentType: "article",
    seo: {
      title: "Zero Trust Architecture in 2026: Enterprise Deployment Guide | Cognify",
      description:
        "A practical look at where enterprise Zero Trust deployments stand in 2026, from identity-centric controls to microsegmentation and service mesh.",
      keywords: [
        "zero trust architecture",
        "ZTA 2026",
        "microsegmentation",
        "ZTNA",
        "SASE",
        "enterprise security",
      ],
      canonicalUrl: null,
      structuredData: null,
    },
    citations: [
      {
        index: 1,
        title: "Cloud Adoption and Network Architecture 2026",
        url: "https://www.gartner.com/en/documents/cloud-network-architecture-2026",
        authors: ["Gartner Research"],
        publishedAt: "2026-01-10T00:00:00Z",
      },
      {
        index: 2,
        title: "NIST SP 800-207: Zero Trust Architecture",
        url: "https://csrc.nist.gov/publications/detail/sp/800-207/final",
        authors: ["Scott Rose", "Oliver Borchert", "Stu Mitchell"],
        publishedAt: "2020-08-11T00:00:00Z",
      },
      {
        index: 3,
        title: "Magic Quadrant for Zero Trust Network Access 2026",
        url: "https://www.gartner.com/en/documents/ztna-magic-quadrant-2026",
        authors: ["Gartner Research"],
        publishedAt: "2026-02-20T00:00:00Z",
      },
      {
        index: 4,
        title: "Zero Trust Impact Report 2026",
        url: "https://www.illumio.com/resource/zero-trust-impact-report-2026",
        authors: ["Illumio Security Research"],
        publishedAt: "2026-02-01T00:00:00Z",
      },
      {
        index: 5,
        title: "Service Mesh Landscape 2026",
        url: "https://www.cncf.io/blog/service-mesh-landscape-2026",
        authors: ["CNCF Technical Advisory Group"],
        publishedAt: "2026-01-25T00:00:00Z",
      },
      {
        index: 6,
        title: "Zero Trust Maturity Model v2.0",
        url: "https://www.cisa.gov/zero-trust-maturity-model",
        authors: ["CISA"],
        publishedAt: "2023-04-11T00:00:00Z",
      },
    ],
    visuals: [],
    authors: ["Cognify AI"],
    domain: "cybersecurity",
    generatedAt: "2026-03-21T05:00:00Z",
    provenance: {
      researchSessionId: "rsess-a002",
      primaryModel: "claude-opus-4",
      draftingModel: "claude-sonnet-4",
      embeddingModel: "all-MiniLM-L6-v2",
      embeddingVersion: "v2.0",
    },
    aiGenerated: true,
    status: "complete",
    wordCount: 0,
    workflow: [
      { name: "Research", durationSeconds: 212 },
      { name: "Outline", durationSeconds: 16 },
      { name: "Drafting", durationSeconds: 71 },
      { name: "Humanization", durationSeconds: 24 },
      { name: "SEO", durationSeconds: 17 },
      { name: "Finalized", durationSeconds: 5 },
    ],
  },
  {
    id: "art-003",
    title: "Transformer Models: State of the Art",
    subtitle: "Surveying the architecture advances driving today's most capable LLMs",
    bodyMarkdown: `## From Attention to Modern Architectures

The transformer architecture, introduced in the 2017 "Attention Is All You Need" paper, replaced recurrent networks with a self-attention mechanism that allows parallel processing of sequence tokens [1]. Seven years later, the core attention operation is still central to every frontier language model, but the surrounding architecture has changed substantially. Positional encodings have moved from absolute sinusoidal embeddings to rotary position embeddings (RoPE) that generalize better to longer contexts [2]. Layer normalization has migrated from post-residual (as in the original transformer) to pre-residual, stabilizing training at scale.

Mixture-of-Experts (MoE) has emerged as the dominant scaling strategy for parameter-efficient models. Rather than activating every parameter for each token, MoE routes each token to a small subset of specialized sub-networks (experts). Mistral AI's Mixtral 8x22B demonstrated that a model activating only 39 billion parameters at inference time could match the performance of dense models with twice the total parameter count [3]. The routing mechanism introduces load balancing challenges—experts must be used roughly equally to prevent collapse—but modern implementations address this with auxiliary balancing losses during training.

## Scaling Laws and What They Predict

Chinchilla scaling laws, published by DeepMind in 2022 and revised in 2025, define the optimal compute allocation between model parameters and training tokens for a given compute budget [4]. The revised guidance suggests that current frontier models are undertrained relative to optimal: for a model with 70 billion parameters, the compute-optimal token count is approximately 1.4 trillion, but most publicly reported training runs used fewer tokens. This has pushed labs toward longer training runs and higher-quality data curation rather than simply scaling parameter counts.

Data quality has become the primary bottleneck at the frontier. The FineWeb dataset from HuggingFace, assembled from 15 trillion Common Crawl tokens through aggressive quality filtering, demonstrated that a model trained on 1 trillion carefully selected tokens outperforms one trained on 3 trillion tokens from a less curated set [5]. Active learning strategies that sample from the data distribution most informative to the current model checkpoint are an active research area, with promising early results from Google and Anthropic.

## Reasoning and Long-Context Capabilities

Chain-of-thought prompting showed that large models can improve on multi-step reasoning tasks by generating explicit intermediate steps before producing a final answer. More recent work on process reward models (PRMs) trains verifiers that score each step of a reasoning trace rather than only the final answer, enabling rejection sampling of high-quality reasoning trajectories [6]. This approach, pioneered in OpenAI's o-series and adopted across the industry, has produced substantial gains on competition mathematics and formal verification benchmarks.

Long-context capabilities have expanded from 4,096 tokens in GPT-3 to over one million tokens in Claude 3.5 and Gemini 1.5 Pro. Positional interpolation techniques allow models trained on shorter sequences to generalize to longer ones with minimal fine-tuning. Practical retrieval quality does degrade for very long contexts—the "lost in the middle" phenomenon where information in the middle of a long document receives less attention—but sliding window attention and hybrid architectures address the worst cases [2].

## References

1. Vaswani et al. — "Attention Is All You Need" (NeurIPS 2017)
2. Su et al. — "RoFormer: Enhanced Transformer with Rotary Position Embedding" (2023)
3. Mistral AI — "Mixtral 8x22B Technical Report" (2025)
4. Hoffmann et al. — "Training Compute-Optimal Large Language Models" (DeepMind 2025 revision)
5. Penedo et al. — "FineWeb: Decanting the Web for the Finest Text Data at Scale" (HuggingFace 2025)
6. Lightman et al. — "Let's Verify Step by Step" (OpenAI 2024)
`,
    summary:
      "Transformer model advances in 2026 center on mixture-of-experts architectures, revised Chinchilla scaling laws emphasizing data quality, and process reward models that enable step-level reasoning verification.",
    keyClaims: [
      "Mixture-of-Experts routing allows a model activating 39B parameters to match dense models with 2x total parameters.",
      "Revised Chinchilla scaling laws indicate most frontier models are undertrained relative to compute-optimal token counts.",
      "A model trained on 1 trillion curated tokens outperforms one trained on 3 trillion less-curated tokens.",
      "Process reward models improve multi-step reasoning by scoring intermediate steps rather than only final answers.",
      "Long-context capabilities have expanded from 4,096 tokens in GPT-3 to over one million tokens in current frontier models.",
    ],
    contentType: "article",
    seo: {
      title: "Transformer Models: State of the Art in 2026 | Cognify",
      description:
        "A technical survey of the key architecture advances in transformer-based LLMs — MoE scaling, Chinchilla revisions, and process reward models.",
      keywords: [
        "transformer models",
        "LLM architecture",
        "mixture of experts",
        "scaling laws",
        "chain of thought",
        "state of the art AI",
      ],
      canonicalUrl: null,
      structuredData: null,
    },
    citations: [
      {
        index: 1,
        title: "Attention Is All You Need",
        url: "https://arxiv.org/abs/1706.03762",
        authors: ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
        publishedAt: "2017-06-12T00:00:00Z",
      },
      {
        index: 2,
        title: "RoFormer: Enhanced Transformer with Rotary Position Embedding",
        url: "https://arxiv.org/abs/2104.09864",
        authors: ["Jianlin Su", "Yu Lu", "Shengfeng Pan"],
        publishedAt: "2023-03-15T00:00:00Z",
      },
      {
        index: 3,
        title: "Mixtral 8x22B Technical Report",
        url: "https://mistral.ai/news/mixtral-8x22b",
        authors: ["Mistral AI"],
        publishedAt: "2025-04-17T00:00:00Z",
      },
      {
        index: 4,
        title: "Training Compute-Optimal Large Language Models",
        url: "https://arxiv.org/abs/2203.15556",
        authors: ["Jordan Hoffmann", "Sebastian Borgeaud", "Arthur Mensch"],
        publishedAt: "2025-02-10T00:00:00Z",
      },
      {
        index: 5,
        title: "FineWeb: Decanting the Web for the Finest Text Data at Scale",
        url: "https://arxiv.org/abs/2406.17557",
        authors: ["Guilherme Penedo", "Hynek Kydlicek", "Loubna Ben Allal"],
        publishedAt: "2025-06-25T00:00:00Z",
      },
      {
        index: 6,
        title: "Let's Verify Step by Step",
        url: "https://arxiv.org/abs/2305.20050",
        authors: ["Hunter Lightman", "Vineet Kosaraju", "Yura Burda"],
        publishedAt: "2024-05-31T00:00:00Z",
      },
    ],
    visuals: [],
    authors: ["Cognify AI"],
    domain: "ai-ml",
    generatedAt: "2026-03-20T10:00:00Z",
    provenance: {
      researchSessionId: "rsess-a003",
      primaryModel: "claude-opus-4",
      draftingModel: "claude-sonnet-4",
      embeddingModel: "all-MiniLM-L6-v2",
      embeddingVersion: "v2.0",
    },
    aiGenerated: true,
    status: "draft",
    wordCount: 0,
    workflow: [
      { name: "Research", durationSeconds: 224 },
      { name: "Outline", durationSeconds: 18 },
      { name: "Drafting", durationSeconds: 79 },
      { name: "Humanization", durationSeconds: 26 },
      { name: "SEO", durationSeconds: 19 },
      { name: "Finalized", durationSeconds: 5 },
    ],
  },
  {
    id: "art-004",
    title: "Cloud Security Best Practices",
    subtitle: "A practical playbook for reducing attack surface across AWS, Azure, and GCP",
    bodyMarkdown: `## The Shared Responsibility Model in Practice

Every major cloud provider publishes a shared responsibility model that divides security obligations between the provider and the customer. The provider secures the infrastructure — physical data centers, hypervisor, managed services — while the customer is responsible for data classification, identity configuration, network controls, and application security. In practice, most cloud security incidents trace back to customer-controlled layers: misconfigured S3 buckets, overly permissive IAM policies, and exposed management ports [1].

The 2026 Cloud Security Alliance report found that 82% of cloud data breaches originated from identity and access management failures — not from vulnerabilities in the cloud platform itself [2]. This reframes the cloud security problem: the technology is largely trustworthy; the configuration is not. Tools like AWS IAM Access Analyzer, Azure Policy, and GCP Security Command Center surface misconfigurations in near-real time, but adoption of these native tools remains patchy. Organizations that centralize cloud security posture management (CSPM) through a dedicated platform see a 58% reduction in critical misconfiguration findings within 90 days of deployment.

## Identity and Least-Privilege at Scale

Managing cloud identity at scale requires a disciplined approach to least-privilege enforcement. Every human user, service account, and workload identity should have only the permissions it demonstrably needs. In practice, teams start with broad permissions and rarely audit them, resulting in permission sprawl: identities that have access to dozens of services they never use [3].

Infrastructure as Code (IaC) tooling has become the most effective lever for enforcing least privilege at provisioning time. When IAM policies are declared in Terraform or Pulumi, they can be reviewed in pull requests, scanned by tools like Checkov or tfsec, and versioned alongside the infrastructure they govern [4]. AWS's recent launch of IAM Access Grants, which allows fine-grained S3 access at the prefix level without inline bucket policies, is a good example of how platform-native primitives are evolving to support this model.

## Network Security and Encryption Baselines

Cloud-native network security centers on security groups, network ACLs, and private endpoints rather than traditional firewall appliances. The key principle is default-deny: all traffic should be blocked unless explicitly allowed, and east-west traffic between services should be as restricted as north-south traffic from the internet [5].

Encryption should be on by default at every layer. AWS reports that 97% of new workloads enable encryption at rest via KMS, a figure that has grown from 61% in 2022 [1]. In transit encryption has reached near-universal adoption for external traffic, but internal service-to-service traffic within a VPC remains a gap at some organizations — an issue that service mesh adoption addresses directly. Key rotation should be automated with annual or shorter rotation periods for customer-managed keys, with rotation events logged and alerted on.

## Continuous Compliance and What to Prioritize First

For organizations early in their cloud security journey, prioritizing a small number of high-impact controls delivers the most risk reduction per engineering hour. The CIS Cloud Benchmarks provide scored, prioritized recommendations for each major provider [6]. The top five for AWS are: enable CloudTrail in all regions, enable GuardDuty, enforce MFA for root and IAM users, block public S3 access by default, and enable Config with a core rule set covering IAM and network configuration.

Automated compliance scanning via AWS Security Hub, Azure Defender for Cloud, or a third-party CSPM tool converts these benchmarks into continuous monitoring rather than a point-in-time assessment. Findings are scored by severity and routed to owning teams via ticketing integrations. Organizations that treat compliance findings as bugs — not audits — and route them through normal development workflows see the fastest remediation velocity.

## References

1. AWS Security — "AWS Cloud Security Report 2026"
2. Cloud Security Alliance — "Top Threats to Cloud Computing 2026"
3. CrowdStrike — "2026 Global Threat Report: Cloud Intrusions"
4. Bridgecrew — "State of Open Source Terraform Security 2026"
5. NIST SP 800-204C — "Implementation of DevSecOps for a Microservices-based Application"
6. CIS — "CIS Benchmarks for Cloud Providers 2026"
`,
    summary:
      "Cloud security in 2026 is primarily an identity and configuration problem, not a platform vulnerability problem; organizations that enforce least-privilege IAM through IaC and adopt CSPM tools see the greatest risk reduction.",
    keyClaims: [
      "82% of cloud data breaches in 2026 originated from IAM failures, not cloud platform vulnerabilities.",
      "Organizations centralizing CSPM see a 58% reduction in critical misconfiguration findings within 90 days.",
      "97% of new AWS workloads now enable encryption at rest via KMS, up from 61% in 2022.",
      "IaC tooling with policy scanning enables least-privilege enforcement at provisioning time through PR review.",
      "Treating compliance findings as bugs and routing them through development workflows produces the fastest remediation velocity.",
    ],
    contentType: "article",
    seo: {
      title: "Cloud Security Best Practices 2026: AWS, Azure, GCP Playbook | Cognify",
      description:
        "A practical guide to cloud security across AWS, Azure, and GCP — covering IAM, least privilege, network controls, encryption, and continuous compliance.",
      keywords: [
        "cloud security",
        "AWS security",
        "IAM least privilege",
        "CSPM",
        "cloud misconfiguration",
        "CIS benchmarks",
      ],
      canonicalUrl: null,
      structuredData: null,
    },
    citations: [
      {
        index: 1,
        title: "AWS Cloud Security Report 2026",
        url: "https://aws.amazon.com/security/cloud-security-report-2026",
        authors: ["AWS Security Team"],
        publishedAt: "2026-01-30T00:00:00Z",
      },
      {
        index: 2,
        title: "Top Threats to Cloud Computing 2026",
        url: "https://cloudsecurityalliance.org/research/top-threats-2026",
        authors: ["Cloud Security Alliance"],
        publishedAt: "2026-02-15T00:00:00Z",
      },
      {
        index: 3,
        title: "2026 Global Threat Report: Cloud Intrusions",
        url: "https://www.crowdstrike.com/global-threat-report/2026",
        authors: ["CrowdStrike Intelligence Team"],
        publishedAt: "2026-02-22T00:00:00Z",
      },
      {
        index: 4,
        title: "State of Open Source Terraform Security 2026",
        url: "https://bridgecrew.io/research/terraform-security-2026",
        authors: ["Bridgecrew Research"],
        publishedAt: "2026-03-05T00:00:00Z",
      },
      {
        index: 5,
        title: "NIST SP 800-204C: Implementation of DevSecOps for a Microservices-based Application",
        url: "https://csrc.nist.gov/publications/detail/sp/800-204c/final",
        authors: ["Murugiah Souppaya", "Karen Scarfone"],
        publishedAt: "2022-08-17T00:00:00Z",
      },
      {
        index: 6,
        title: "CIS Benchmarks for Cloud Providers 2026",
        url: "https://www.cisecurity.org/benchmark/amazon_web_services",
        authors: ["Center for Internet Security"],
        publishedAt: "2026-01-08T00:00:00Z",
      },
    ],
    visuals: [],
    authors: ["Cognify AI"],
    domain: "cybersecurity",
    generatedAt: "2026-03-19T10:00:00Z",
    provenance: {
      researchSessionId: "rsess-a004",
      primaryModel: "claude-opus-4",
      draftingModel: "claude-sonnet-4",
      embeddingModel: "all-MiniLM-L6-v2",
      embeddingVersion: "v2.0",
    },
    aiGenerated: true,
    status: "published",
    wordCount: 0,
    workflow: [
      { name: "Research", durationSeconds: 198 },
      { name: "Outline", durationSeconds: 15 },
      { name: "Drafting", durationSeconds: 68 },
      { name: "Humanization", durationSeconds: 22 },
      { name: "SEO", durationSeconds: 16 },
      { name: "Finalized", durationSeconds: 4 },
    ],
  },
];

// Compute wordCount from bodyMarkdown at module load time
mockArticleDetails.forEach((article) => {
  article.wordCount = article.bodyMarkdown.split(/\s+/).filter(Boolean).length;
});

export const articleListItems: ArticleListItem[] = mockArticleDetails.map((a) => ({
  id: a.id,
  title: a.title,
  summary: a.summary,
  domain: a.domain,
  status: a.status,
  wordCount: a.wordCount,
  generatedAt: a.generatedAt,
}));
