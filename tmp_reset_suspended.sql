-- Local-only cleanup: a prior full run of the ToS-decline test suspended the
-- independent.student@iqbalai.dev identity (intended behavior of that test),
-- which then breaks subsequent local re-runs of the per-role journey test
-- against the same persistent dev DB. Reset it back to active so re-runs are
-- clean. This has no bearing on CI (fresh DB every run).
update independent.independent_users
set status = 'ACTIVE'
where email = 'independent.student@iqbalai.dev';

select email, status from independent.independent_users where email = 'independent.student@iqbalai.dev';
