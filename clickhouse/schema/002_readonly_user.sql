CREATE USER IF NOT EXISTS mediadoc_readonly IDENTIFIED WITH plaintext_password BY 'mediadoc_readonly_pw';

GRANT SELECT ON mediadoc.* TO mediadoc_readonly;

CREATE SETTINGS PROFILE IF NOT EXISTS mediadoc_readonly_profile
    SETTINGS readonly = 1, max_execution_time = 30, max_result_rows = 100000 TO mediadoc_readonly;
