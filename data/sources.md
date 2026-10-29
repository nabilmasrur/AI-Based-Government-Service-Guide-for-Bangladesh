# Source log

Every entry in `passport.json` and `licence.json` must be checked against an official
page before its `verified_on` date is set. Record each check here so a second team
member can repeat it.

## Official sources

| Domain | Authority | URL |
|---|---|---|
| Passport | Department of Immigration & Passports | https://www.epassport.gov.bd/ |
| Passport | DIP main site | https://dip.gov.bd/ |
| Licence | Bangladesh Road Transport Authority | https://brta.gov.bd/ |
| Licence | BRTA Service Portal (BSP) | https://bsp.brta.gov.bd/ |

## Verification log

Add one row per entry as you check it. `verified_on` in the JSON must match the date here.

| Entry id | Checked against | Checked by | Date | Notes |
|---|---|---|---|---|
| passport.new.documents | | | | |
| passport.new.office | | | | |
| passport.new.fee | | | | **Seed figures came from a secondary source — re-check every number** |
| passport.new.timeline | | | | |
| passport.new.online_steps | | | | |
| passport.new.biometric | | | | |
| passport.reissue.documents | | | | |
| passport.reissue.note | | | | |
| passport.reissue.fee | | | | |
| passport.correction.documents | | | | |
| passport.correction.note | | | | |
| passport.lost.documents | | | | |
| passport.lost.note | | | | |
| passport.mrp_to_epp.documents | | | | |
| passport.mrp_to_epp.note | | | | |
| passport.delivery.fee | | | | |
| passport.status.online_steps | | | | |
| licence.learner.documents | | | | |
| licence.learner.office | | | | |
| licence.learner.fee | | | | Seed text points at the BRTA schedule instead of quoting amounts — replace with the real figures once checked |
| licence.learner.timeline | | | | |
| licence.learner.online_steps | | | | |
| licence.smartcard_new.documents | | | | |
| licence.smartcard_new.fee | | | | |
| licence.smartcard_new.timeline | | | | |
| licence.renewal.documents | | | | |
| licence.renewal.note | | | | |
| licence.duplicate.documents | | | | |
| licence.duplicate.note | | | | |
| licence.category_change.documents | | | | |
| licence.category_change.note | | | | |
| licence.exam.note | | | | |
| licence.exam.timeline | | | | |
| licence.idp.documents | | | | |
| licence.idp.note | | | | |

## Rules the team agreed

1. Fees and processing times come from an official page only — never a blog, a coaching
   centre, or a driving school site.
2. The person who wrote an entry may not be the person who verifies it.
3. If an official page and a secondary source disagree, the official page wins and the
   disagreement is noted above.
4. If a figure cannot be confirmed, the entry says where to check rather than quoting a
   number. An honest pointer beats a confident wrong answer.
