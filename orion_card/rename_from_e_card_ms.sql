-- Run once per site BEFORE the first `bench migrate` after renaming the app
-- from e_card_ms to orion_card:
--
--   bench --site <site> mariadb < apps/orion_card/orion_card/rename_from_e_card_ms.sql
--
-- Frappe can't start while installed_apps names a package that no longer
-- exists, so these are done with plain SQL. Everything else is done by the
-- orion_card.patches.rename_from_e_card_ms patch during migrate.
-- Safe to run twice.

SET SQL_SAFE_UPDATES = 0;

UPDATE `tabDefaultValue`
SET defvalue = REPLACE(defvalue, '"e_card_ms"', '"orion_card"')
WHERE defkey = 'installed_apps' AND parent = '__global';

UPDATE `tabInstalled Application` SET app_name = 'orion_card' WHERE app_name = 'e_card_ms';

-- Already-run patches keep counting as run under the new name.
UPDATE `tabPatch Log`
SET patch = CONCAT('orion_card', SUBSTRING(patch, CHAR_LENGTH('e_card_ms') + 1))
WHERE patch LIKE 'e\_card\_ms.%';
