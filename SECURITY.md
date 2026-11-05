# LifeTrip — Security review context

Check user-session state isolation, crossing permission L0-L2 boundaries, unintended location disclosure, malicious URL/path, travel/time/weather source freshness, provider outages and maps API calls. No silent task transitions or location data sent beyond authorized providers.

Use isolated synthetic fixtures; do not touch real personal/customer data, remote secrets or production deployments. Report exact source and unsafe input, observed impact, minimal reproduction and severity; do not present absent planned features as existing vulnerabilities. Sensitive reports go privately to owner or GitHub private advisories if enabled; no public secrets/exploits. Preserve owner approval for live changes.
