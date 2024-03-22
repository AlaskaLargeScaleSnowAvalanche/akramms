# Stuff to create the PostGIS database


def init_db_sql():
    return """
        -- Must be done from postgres user
        CREATE EXTENSION postgis;
        -- https://www.postgresql.org/docs/current/btree-gist.html
        create extension btree_gist;
    """


def create_tables_sql(expmod):

    exp = expmod.name
    cols = [('exp', 'varchar(20)')] + [(key, expmod.combo_sql_types[key]) for key in expmod.combo_schema.schema.keys()]
    cols = cols[:-2]    # Exclude idom/jdom
    cols_sql = ','.join(f'{col}' for col,_ in cols)
    cols_types_sql = ',\n'.join(f'{col} {dtype} not null' for col,dtype in cols)

    sql = f"""
        -- List the combos in this experiment
        drop table {exp}_wcombos cascade;
        create table {exp}_wcombos (
            wcomboid serial UNIQUE,
            {cols_types_sql},
            PRIMARY KEY({cols_sql}));

        -- Keep track of which combos we've uploaded
        drop table {exp}_combos;
        create table {exp}_combos (
            wcomboid int not null references {exp}_wcombos(wcomboid) on delete cascade,
            idom int not null,
            jdom int not null,
            archive_ts timestamp,
            upload_ts timestamp,
            PRIMARY KEY(wcomboid, idom, jdom));

        -- Store avalanches by wcombo
        drop table {exp}_avals;
        create table {exp}_avals (
            wcomboid int not null references {exp}_wcombos(wcomboid) on delete cascade,
            idom int not null,
            jdom int not null,
            pra_size char(1) not null,
            avalid int not null);
        create unique index {exp}_avals_idx on {exp}_avals(wcomboid, avalid);
        SELECT AddGeometryColumn('{exp}_avals', 'extent', '{expmod.epsg}', 'MULTIPOLYGON', 2);
        CREATE INDEX {exp}_extent_idx ON {exp}_avals USING GIST (wcomboid, extent);
    """

    return sql;

def load_avals(expmod, akdf):
    """
    akdf:
        Resolved to ID
    """



def loaddb(akdf0):
    """
    akdf0:
        Resolved to combo
    """
    # Resolve to the avalanche (ID) level
    akdf0 = resolve.resolve_chunk(akdf0, scenetypes={'arc'})
    akdf0 = resolve.resolve_id(akdf0, realized=True, status_col=True)
    akdf0 = akdf1[akdf0.id_status == file_info.JobStatus.FINISHED]

    sqls = list()    # Lines of sql
    for (exp,combo),akdf1 in akdf0.reset_index(drop=True).groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)

        # TODO:
        1. Set up a wcomboid in the database
        2. Read each avalanche
        # 2. Upload to ak_combos to show we've finished this off

        for tup in akdf1.itertuples(index=False):

            arcdir = tup.releasefile
            if not os.path.isfile(tup.avalfile):
                raise ValueError(f'Missing avalanche file: {tup.avalfile}')

            print(f'loaddb: {tup.avalfile}')

            with netCDF4.Dataset(tup.avalfile) as nc:
                nc.set_always_mask(False)


            










#It looks like I need a "gist" index
#https://stackoverflow.com/questions/37125087/combining-traditional-and-spatial-indices-in-postgres


def main():
    import akramms.experiment.ak
    expmod = akramms.experiment.ak
    sql = create_tables_sql(expmod)

    with open('sql','w') as out:
        out.write(sql)

main()
