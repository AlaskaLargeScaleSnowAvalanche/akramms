def XXXXXXXXX_query_overruns(release_files, ids=None):
    print('Fetching job statuses...')
    df = job_statuses(release_files)    # index=id
    df = df[df.job_status == JobStatus.OVERRUN]
    all_ids = list()
    for id,row in df.iterrows():
        jb = row.jb
        run_dir = jb.avalanche_dir
        job_name = f"{jb.ramms_name}_{row['id']}"
        if ids is None or row['id'] in ids:
            all_ids.append(id)
            continue

        # ONLY enlarge if the .out.zip file is newer than the .in.zip file
        # (Otherwise, we apparently already enlarged but have not yet re-run)
        out_zip = os.path.join(run_dir, f'{job_name}.out.zip')
        in_zip = os.path.join(run_dir, f'{job_name}.in.zip')
        out_zip_tm = os.path.getmtime(out_zip)
        try:
            in_zip_tm = os.path.getmtime(in_zip)
            if out_zip_tm > in_zip_tm:
                all_ids.append(id)
        except OSError:    # File not exist
            # This shouldn't normally happen
            in_zip_tm = -1
            print(f'Input file missing: {in_zip}')

    # Cut down the query
    return df[all_ids]



def xxxxxx_enlarge_domain(run_dir, job_name, enlarge_increment=5000.):
    zip_fname = os.path.join(run_dir, job_name+'.in.zip')
    print(f'Enlarging domain in: {zip_fname}')

    with zipfile.ZipFile(zip_fname, 'a') as in_zip:
        latest_arcname = latest_dom_file(in_zip.namelist())    # Eg: {job_name}.v1.dom
        next_arcname = incr_dom_file(latest_arcname)
        print(f'{job_name}: reading {latest_arcname}')
        dom0 = rammsutil.read_polygon_from_zip(in_zip, latest_arcname)
        dom1 = rammsutil.add_margin(dom0, enlarge_increment)

        with np.printoptions(precision=0, suppress=True):
            print('{}:\n  {} -> {}'.format(job_name, rammsutil.edge_lengths(dom0), rammsutil.edge_lengths(dom1)))

        rammsutil.write_polygon_to_zip(dom1, in_zip, next_arcname)

    # Resubmit with the expanded domain
    print('Resubmitting: {}/{}'.format(run_dir, job_name))
    submit_job(run_dir, job_name)


def enlarge_domains(parseds):
    akdf0 = resolve.resolve_to(
        parseds, args.level, level='combo', scenetypes={'x'}, realized=True)

    # Separate by experiment (usually only one)
    for exp,akdf1 in akdf0.groupby('exp'):
        expmod = parse.load_expmod(exp)

        # Separate by combo (AKRAMMS scene)
        for combo,akdf2 in akdf1.groupby('combo'):
            scenedir = expmod.combo_to_scenedir(combo)

            # Determine most recent chunktype, and the one we will write to
            # (TODO: Reuse this code somewhere)
            max_id = -1
            for name in os.listdir(scenedir)
                match = _chunktypeRE.match(name)
                if match is not None:
                    sid = matc.group(1)
                    id = 0 if sid is None else int(sid)
                    max_id = max(max_id, id)
            #last_chunktype = 'CHUNKS' if max_id==0 else f'CHUNKS{max_id}'
            #next_chunktype = f'CHUNKS{max_id+1}'

            # Generate Avalanche IDs
            akdf3 = resolve.resolve_chunk(
                akdf2, scenetypes={'x'}, chunktypes={last_chunktype})
            akdf3 = resolve.resolve_id(akdf3, realized=True)
            akdf3 = resolve.remove_overrun_dups(akdf3)
            akdf3 = akdf3.set_index('id')    # Works only within one combo

            # Add a 'jobstatus' and 'jbkey' columns to the dataframe
            akdf3 = jobolib.add_job_status(scenedir, akdf3)

            # Filter out by jobstatus
            akdf3 = akdf3[akdf3.jobstatus == joblib.JobStatus.OVERRUN]

            # Read the releasefile columns for whatever remains
            akdf3 = resolve.read_releasefiles(akdf3)

            # Uses resulting set of avalanches to generate a chunk
            for sizecat,akdf4 in akdf3.groupby('sizecat'):
TODO: Generate chunk in existing CHUNKS directory, based on largest existing chunk number (for this sizecat)
TODO: Actually enlarge the domain!!!!
                rp = scene_args['return_periods'][0]    # There is only 1
                For = 'For' if scene_args['forests'][0] else 'NoFor'
                res = scene_args['resolution']
                chunkname = scenedir.parts[-1] + f'00000{rp:d}{sizecat}{For}_{res}m'
                chunkdir = scenedir / next_chunktype / chunkname

                # Uses data in akdf4 to generate a chunk ready for RAMMS Stage 1
                generate_chunk(akdf4, chunkdir)
