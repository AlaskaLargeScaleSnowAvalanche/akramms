

# Queries avalanches in their RAMMS form, without archiving.

def query_release_files(release_files, filter_in_fn=rammsfilter.all):

    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        ids = get_job_ids(release_file)

        for id in ids:
            out_zip = os.path.join(jb.avalanche_dir, f'{job_name}.out.zip')

            # Only process if the avalanche has run
            if not os.path.exists(out_zip):
                continue

            # Apply user filter
            if filter_in_fn(jb, id):
                yield out_zip

def query_aspecs(aspecs, filter_in_fn=ramsfilter.all):
    for aspec in aspecs:
        return query_release_files(
            exputil.release_files(aspec.exp_mod, apsec.combo),
            filter_in_fn=filter_in_fn)

