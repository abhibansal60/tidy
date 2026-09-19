# YouTube API policy research for Jev

Fetched: 2026-09-19. Sources are Google/YouTube primary pages only. Policy pages (Developer Policies, ToS, derived-metrics policy, quota page, revision history, sensitive-scope page) were re-read from raw HTML, not only from summaries. This is a reading of the text, not legal advice. Items marked **UNCLEAR** need the owner to decide or Google to clarify (via the YouTube API Services contact form).

Abbreviations: DP = [Developer Policies](https://developers.google.com/youtube/terms/developer-policies) (page "Last updated 2026-09-14"); ToS = [API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service) (2026-09-14); DMP = [Additional policies for derived metrics and data storage](https://developers.google.com/youtube/terms/derived-metrics-policy) (2026-09-14).

## Summary answers

1. **Derived data.** DP III.E.4.h forbids using API Data "to create new or derived data or metrics", and gives "a score that factors in likes, total views, or any other API Data" as a prohibited example. An LLM judgment about channel metadata is most safely treated as derived data. The only relief is the DMP amendment. **UNCLEAR** whether a yes/no probability judgment counts as a "metric" at all.
2. **Refresh and deletion.** Stored API Data: delete or refresh every 30 calendar days. On user deletion request or account deletion: within 7 days. After access revocation: within 30 days. Deleted or private content has no separate rule beyond "consistent with current data"; delete on 404/private.
3. **Storing.** Non-Authorized (public, API-key) data: "temporarily" and "limited amounts", max 30 days. Authorized data (OAuth, e.g. your subscription list): 30 days too, except statistics. Nothing transient is restricted; the 30-day rule is the ceiling for anything persisted.
4. **Third-party AI.** No AI, ML, training or sub-processor text exists in the DP or ToS. Sharing must be disclosed in a privacy policy. Authorized Data must not be shown to anyone but the user "or agents expressly approved by that user". **UNCLEAR** whether an LLM API is an "agent"; for a personal tool the owner approves it.
5. **Derived-metrics amendment.** Allows custom scores, tagging, sentiment, brand suitability, and 36-month storage of derived metrics. DP III.L says it applies "only to audited developers with analytics use cases" who applied via the quota-extension form. Personal use is not excluded but is not obviously eligible. **UNCLEAR.**
6. **Public write-up.** No rule directly governs a blog post. Risky parts: publishing derived judgments about identifiable channels, and DP III.E.2 aggregation. Aliased channels and owner-only counts are the low-risk path. **UNCLEAR** whether a write-up is an "API Client" display.
7. **Subscribe/unsubscribe.** Not prohibited. DP requires "the user's prior specific and express consent" for automated actions. Quota: 50 units each for insert and delete. `search.list` costs 1 unit but only 100 calls/day by default. `featuredChannelsUrls` was removed.
8. **Reuse.** Open source is fine, but do not embed your credentials. Each runner uses their own API project and OAuth client. A hosted service needs a privacy policy, ToS acceptance, deletion flow, OAuth verification for the sensitive `youtube` scope, and probably an API audit for more quota. Testing-mode OAuth refresh tokens last 7 days.
9. **Design.** Store owner labels (channel ID plus decision, no API text). Cache API metadata and judgments with a hard 30-day expiry and a purge command. Keep judgments transient or short-lived.

---

## 1. Derived data and LLM judgments

- DP III.E.4.h: API Clients "must not (i) replace API Data with similar, independently calculated data, or (ii) access or use API Data to create new or derived data or metrics."
- Same section, example: "you are not permitted to use the number of likes returned in the API Data to calculate other metrics, such as ... a score that factors in likes, total views, or any other API Data." Content not based on API Data may be shown alongside it only with "a clear and prominent disclosure" that it is "not from YouTube and [is] part of your own product."
- DMP intro: "you are generally prohibited from creating metrics that replace or modify the data returned by the YouTube API Services." Relief only "subject to your acceptance of the amendment." Listed examples include "Content Categorization and Tagging" (custom sub-genres/tags, "clearly disclosed to the user that they are your tags"), custom scores, sentiment analysis (NLP on comments is named), and brand suitability.
- DMP storage: derived metrics "(such as sentiment analysis) based on retrieved data may also be stored for up to 36 calendar months" for accepted clients. "Other data (such as video titles, creator names, descriptions, and comment text) must still follow the 30-day refresh and deletion policy."
- DMP sensitive-attribute limit: no inferring "age, race, religious affiliation, political leaning, sexual orientation, or health status" of the audience or creator. Jev's prompts should avoid such judgments.

Reading: the text was written with numeric metrics in mind. An LLM probability that a channel matches a topic is a "new or derived" datum in ordinary reading, and category tagging is exactly what the DMP allows only after acceptance. Without acceptance, keep it ephemeral or under the 30-day cap.

**UNCLEAR / needs Google:** whether typed LLM classifications are "derived data or metrics" under III.E.4.h, and whether the 30-day cap or the general prohibition governs them.

## 2. Refresh and deletion windows

- DP III.E.4.c: other Authorized Data may be stored "for no longer than 30 calendar days. After 30 calendar days, the API Client must either delete or refresh the stored data."
- III.E.4.d: Non-Authorized Data, "not longer than 30 calendar days" (same delete-or-refresh rule).
- III.E.4.e: "must use reasonable efforts to ensure that their stored API Data is consistent with the current data."
- III.E.4.b (statistics): may be kept longer, but the client "must still ensure every 30 days that it is still authorized" and "verify, every 30 days, that the video has not been deleted." This exception covers only Authorized Data; "must not store statistics retrieved as Non-Authorized Data for more than 30 days."
- User request or account deletion: "as soon as possible and within 7 calendar days" (III.E.4.g). The client must offer a way to request deletion.
- Revocation: clients must "delete API Data associated with users whose authorization tokens cannot be refreshed ... within 30 calendar days of that revocation" (III.D.2, user authentication section).
- ToS 24.3: on termination or suspension, "immediately stop ... and delete all YouTube API Services (including all API Data)".

**UNCLEAR:** no explicit rule for a channel or video that becomes deleted or private beyond the freshness duty. The conservative reading is to purge it on the next refresh that returns not-found or private.

## 3. Storing API data at all

- Public data fetched with an API key is Non-Authorized Data ("accessible by an API Client without User Credentials", DP definitions). It may be stored only "temporarily", in "limited amounts", for up to 30 days.
- Your subscription list (`subscriptions.list mine=true`) is Authorized Data: 30 days, with the statistics exception above.
- Tokens: "may store authorization tokens for as long as is necessary" for the consented purposes (III.E.4.a).
- Anything used transiently in memory during a run is not restricted.
- DP "Respect users' privacy" guidance: "Don't store user data indefinitely."

**UNCLEAR:** "limited amounts" has no numeric bound. Channel IDs are API Data in principle; the policy does not say whether a bare ID kept in a personal label needs expiry.

## 4. Sending metadata to a third-party AI service (TypeSafe)

- I found no mention of AI, machine learning, training or sub-processors in the DP or ToS (searched the raw text).
- ToS 7: a published privacy policy must describe "how and why you and your API Client use, process, and share such information ... with us and other third parties." DP III.A.2: explain "how the information is shared with either internal or external parties."
- DP III.E.3: "must not display or allow access to Authorized Data to anyone other than the authorizing user or agents expressly approved by that user." Public metadata is not Authorized Data; your subscription list is. Send the LLM only public channel/video metadata plus a channel ID, not the subscription relationship, where possible.
- ToS 8 and DP security: protect API Data "from unauthorized access, use, or disclosure."
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy) (page dated Feb 15, 2024): its Limited Use section restricts transfers of user data obtained through "the product's specified scopes" and covers data "aggregated, anonymized, or derived from them." It does not mention YouTube or generative AI. **UNCLEAR** whether it applies to YouTube scopes. The YouTube DP and ToS do not cite it.
- TypeSafe's own retention and training terms are outside these sources; the owner must check them.

## 5. The derived-metrics amendment

- DP III.L: "only applicable to audited developers with analytics use cases that have explicitly applied for permission to create additional metrics and/or store statistical data through the standard quota extension request form (starting June 01, 2026)."
- DMP: accept the amendment by selecting "Section 5: Use Cases, API Integration, and Feature Implementation" then "Analytics & Reporting" on the API contact form. It also states "Your API Service must reflect an analytics use case on YouTube." Violations "may result in API quota reduction or termination of your API access."
- Effect: 36-month storage for statistical metrics and derived metrics. Titles, descriptions and comment text remain at 30 days.
- No mention of commercial-only eligibility, and no explicit exemption for personal projects.
- Revision history (per fetched summary, not re-verified from raw HTML): introduced May 4, 2026, storage clarification June 1, 2026.

**UNCLEAR:** (a) whether a private curation tool is an "analytics use case"; (b) whether an unaudited, default-quota project can apply, since the audit is tied to quota extension ([audit page](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits): "If you would like to request additional quota beyond the default allocation, you must first complete an audit"); (c) the DP says "audited developers", the DMP says accept via the form. The two pages do not clearly agree. Ask Google.

## 6. Public write-up with aggregates and aliased examples

- No DP or ToS clause targets a blog post. DP III.G lets you "distribute and display YouTube audiovisual content and accompanying metadata to users through your API Clients" if compliant.
- DP III.E.2: "Do not aggregate API Data or otherwise use API Data or YouTube API Services to gain insights into YouTube's usage, revenue, or any other aspects of YouTube's business." Counts about one person's subscriptions are not obviously that, but avoid platform-wide claims.
- Judgments shown publicly are derived data (section 1). If displayed, the DP disclosure rule ("not from YouTube ... your own product") applies. DMP adds: do not "misrepresent API Data's definition or provenance", and do not frame comparisons so they foster "harassment or brigading."
- Aliasing removes the channel-level API Data and the reputational exposure of naming channels.
- Owner's own counts (labels, keep/unsubscribe totals) are the owner's decisions, not API Data. Aggregates of LLM judgments are derived.

**UNCLEAR:** whether a write-up is a regulated display; whether aggregate statistics of judgments are allowed without the amendment. Lowest risk: publish owner-label counts and method description; show aliased examples with no verbatim titles or descriptions.

## 7. Automated subscribe/unsubscribe, quota, discovery

- DP III.I (misuse): "you must not automate or trigger views, uploads, comments, likes, dislikes, or other actions without the user's prior specific and express consent." Automation with express consent is not banned.
- DP III.E.3: clients "must clearly identify any actions that they take to insert, share, update, or delete data ... on the authorizing user's behalf. In addition, the user must expressly consent to those actions prior to their actual execution." A dry-run list plus explicit owner confirmation satisfies this.
- DP III.F: clients "must not offer or provide incentives, rewards, or other compensation to users for engaging ... by ... subscribing to channels." Not applicable to your own account, but do not build subscribe-for-reward features.
- I found no policy on "manipulating subscriptions" other than the above and the ToS abuse language (misuse or interfering with the API).
- Quota ([quota page](https://developers.google.com/youtube/v3/determine_quota_cost), updated 2026-09-15): default is "100 search.list calls, 100 videos.insert calls, and 10,000 units per day combined for all other endpoints"; resets midnight PT.
  - `subscriptions.insert`: "quota cost of 50 units" ([docs](https://developers.google.com/youtube/v3/docs/subscriptions/insert)). Errors include `subscriptionForbidden` ("Too many recent subscriptions").
  - `subscriptions.delete`: "quota cost of 50 units" ([docs](https://developers.google.com/youtube/v3/docs/subscriptions/delete)); 404 if not found.
  - Reads (`subscriptions.list`, `channels.list`, `videos.list`, `playlistItems.list`): 1 unit each. About 200 writes per day fit the default if nothing else is used.
- `search.list`: "quota cost of 1 unit in the Search Queries quota bucket", "100 calls per day" ([docs](https://developers.google.com/youtube/v3/docs/search/list)). Since June 1, 2026 it has its own bucket ([revision history](https://developers.google.com/youtube/v3/revision_history)). Do not rely on older 100-units-per-call figures. 100 searches per day is the discovery ceiling.
- Featured channels: `brandingSettings.channel.featuredChannelsTitle` and `featuredChannelsUrls[]` "are also no longer supported via the API" (revision history, deprecation entry dated May 12, 2021 in the fetched summary). Not usable for discovery. `channelSections` still lists a `multipleChannels` section type (1 unit per list call), but I did not verify that it returns useful data. **UNCLEAR.**

**UNCLEAR:** whether one approved batch counts as "specific" consent per action. Safer: show the exact channels, require an explicit confirm, log each action.

## 8. Reusability: open source vs hosted

Shared facts:
- DP (credentials): "you must not share or disclose your API Credentials to any other third party ... or embed your API Credentials in open source projects." Also "exactly one (1) API Project for that API Client." So the repo must ship no keys, and each user creates their own Cloud project, key and OAuth client.
- DP: "only request access to authorization scopes that they currently use"; do not future-proof.
- Scopes: `youtube.readonly` reads subscriptions. `youtube` or `youtube.force-ssl` is required for insert/delete (docs list `youtubepartner`, `youtube`, `youtube.force-ssl`). Ship read-only by default; request the write scope only for the unsubscribe command.
- Classification: the [sensitive-scope page](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification) says "Examples of sensitive scopes include ... deleting a YouTube video." The scopes reference lists `youtube` as "Manage your YouTube account" and does not show a sensitivity label in text. **UNCLEAR:** confirm each scope's label (sensitive or restricted) in the Cloud Console consent-screen scopes page. I found no indication that YouTube scopes are "restricted" (which would add a security assessment).
- Verification exceptions: "Personal use ... if you are the only user of your app or if your app is used by only a few users, all of whom are known personally to you"; and "if your app is in the development, testing, or staging phases, verification isn't required."
- Testing mode ([OAuth expiry rules](https://developers.google.com/identity/protocols/oauth2#expiration)): external app with status Testing is "issued a refresh token expiring in 7 days" unless only basic profile scopes. Other invalidation causes: revocation, six months unused, exceeded live-token limit. Testing also has a tester warning screen and a user cap. Publishing to production removes the Testing 7-day rule; unverified production apps still show the unverified warning and user cap. Full verification needs a privacy policy, a demo video and domain verification.

Open-source, self-run (each user uses their own project): policy burden is on each runner as their own API Client developer. Recommend the README states the 30-day expiry, no shared credentials, and each runner's ToS acceptance. No audit or verification is needed for personal use at default quota.

Hosted multi-user: you become the API Client for all users, so additionally:
- Published privacy policy, prominently linked, referencing the Google Privacy Policy, describing YouTube API use, collection, sharing (including with the AI vendor), and how to revoke at Google security settings (DP III.A.2). Users must agree before use; link the YouTube ToS.
- Deletion request flow within 7 days; token-revocation purge within 30 days.
- OAuth app verification for sensitive scopes, privacy-policy URL in the OAuth config ([User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)).
- API Compliance Audit for quota beyond defaults (DP III.D.3).
- Per-user isolation of Authorized Data (III.E.3.b).
- Limited Use / transfer rules from the User Data Policy (see section 4, **UNCLEAR** applicability).

## 9. Bottom line: retention design

Design for the strict reading (30-day cap on API-derived data, no DMP amendment):

| Data | Store? | Expiry |
|---|---|---|
| OAuth refresh token | Yes, local file, mode 600 | Until revoked; delete on revoke |
| Owner labels: channel ID, decision, timestamp, note | Yes | Indefinite (owner's own data). Do not copy titles or descriptions |
| Raw API metadata (descriptions, titles, dates) | Cache only if needed for reruns | `fetched_at` column; purge at startup and daily; max 30 days |
| Subscription list snapshot | Yes | 30 days |
| LLM judgments | Either transient, or stored with `fetched_at` = source fetch time | Hard-expire with the source data (max 30 days); never outlive it |
| Aggregate results for write-up | Owner-label counts only | Owner's discretion |

Also add a `purge` command that deletes all API Data, cache and judgments now (covers the 7-day user-deletion duty and the revoke-within-30-days duty), and re-verify authorization and existence on refresh (drop 404/private channels).

Fallback "transient judgments + owner labels kept" is the compliant default: it needs no amendment and no expiry logic beyond the raw cache, and the owner labels are the durable ground truth. Its cost is that experiments cannot compare judgments across runs older than 30 days; rerun instead. Storing judgments beyond 30 days is only defensible after DMP acceptance (up to 36 months for derived metrics, but not for titles or descriptions), and that acceptance is **UNCLEAR** for a personal, unaudited project. Storing judgments up to 30 days alongside their source data is a reasonable middle path.

## Open questions

1. Are LLM classification outputs "derived data or metrics" (DP III.E.4.h) or ordinary content tags (DMP category 3)? Ask Google.
2. Can an unaudited, personal, non-commercial project accept the DMP amendment (DP III.L says "audited developers"; DMP says use the contact form)?
3. Is sending Authorized Data (subscription list) to an LLM vendor covered by "agents expressly approved by that user" (III.E.3.b)?
4. Does the Google API Services User Data Policy (Limited Use, no mention of YouTube or AI) apply to YouTube scopes?
5. Is a public write-up an "API Client" display, and are aggregate statistics of judgments permitted without the amendment (III.E.2 aggregation limits)?
6. Rule for deleted or private content beyond the 30-day freshness duty, and whether bare channel IDs need expiry.
7. Confirm the sensitive vs restricted label for `youtube`, `youtube.readonly` and `youtube.force-ssl` in the Cloud Console.
8. Does one confirmed batch satisfy "prior specific and express consent" for each subscribe/unsubscribe action?
9. Whether `channelSections` (`multipleChannels`) still returns usable featured-channel data for discovery.
10. TypeSafe's data retention and training terms (outside YouTube policy; owner to check).
