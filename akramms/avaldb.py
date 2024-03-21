# Stuff to create the PostGIS database

def create_tables_sql(expmod):>

    exp = expmod.name
    cols = [('exp', 'varchar(20)')] + [(key, expmod.combo_sql_types[key]) for key in expmod.combo_schema.keys()]
    cols_sql = ','.join('{col}' for col,_ in cols)
    cols_types_sql = ','.join('{col} {dtype} not null' for col,dtype in cols)

    sql = f"""

        -- List the combos in this experiment
        create table {exp}_combos (
            comboid serial,
            {cols_types_sql},
            PRIMARY KEY({cols_sql});

        -- Store avalanches by combo
        create table {exp}_combos (
            comboid serial,
            avlaid int,
            UNIQUE KEY(comboid, avalid));
        SELECT AddGeometryColumn('{exp}_avals', 'extent', '{expmod.epsg}', 'MULTIPOLYGON', 2);
        CREATE INDEX {exp}_extent_idx ON {exp}_combos USING GIST (comboid, extent);
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
