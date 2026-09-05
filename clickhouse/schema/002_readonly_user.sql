CREATE USER IF NOT EXISTS cineops_readonly IDENTIFIED WITH plaintext_password BY 'cineops_readonly_pw';

GRANT SELECT ON cineops.* TO cineops_readonly;

CREATE SETTINGS PROFILE IF NOT EXISTS cineops_readonly_profile
    SETTINGS readonly = 1, max_execution_time = 30, max_result_rows = 100000 TO cineops_readonly;
