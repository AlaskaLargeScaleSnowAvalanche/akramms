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
        create table {exp}_wcombos (
            wcomboid serial,
            {cols_types_sql},
            PRIMARY KEY({cols_sql}));

        -- Keep track of which combos we've uploaded
        create table {exp}_combos (
            wcomboid int references {exp}_wcombos(wcomboid) on delete cascade,
            idom int,
            jdom int,
            PRIMARY KEY(wcomboid, idom, jdom));

        -- Store avalanches by wcombo
        create table {exp}_avals (
            wcomboid int references {exp}_wcombos(wcomboid) on delete cascade,
            avlaid int);
        create unique index {exp}_avals_idx on {exp}_avals(wcomboid, avalid);
        SELECT AddGeometryColumn('{exp}_avals', 'extent', '{expmod.epsg}', 'MULTIPOLYGON', 2);
        CREATE INDEX {exp}_extent_idx ON {exp}_avals USING GIST (wcomboid, extent);
    """


    return sql;




#It looks like I need a "gist" index
#https://stackoverflow.com/questions/37125087/combining-traditional-and-spatial-indices-in-postgres


def main():
    import akramms.experiment.ak
    expmod = akramms.experiment.ak
    sql = create_tables_sql(expmod)

    print(sql)

main()
