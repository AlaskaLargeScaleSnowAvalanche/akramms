<!-- BEGIN split_long_polygons.tpl input_layer={input_layer}, output_layer={output_layer}, val_scale={val_scale} -->
						<ProcBase Name="release with Length/Width > 3  and Standard deviation DEM &lt; 30  at  {input_layer}: multi-resolution: 60 [shape:0.6 compct.:1.0] creating '{output_layer}'" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="6534F2E1-485B-406f-B990-350824399FA8">
								<Params>
									<DValue value="1" type="bool" name="bDoOverwrite"></DValue>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="{output_layer}" bVrbl="0">
									<Assignment MapLvl="2" MapName="main"></Assignment>
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue value="3" type="int" name="eLvlUsage"></DValue>
									<DValue value="5" type="int" name="iCompMode"></DValue>
									<DValue type="vector" name="vImgLayerWghtVarOrValue">
									<Values>
									<DValue type="vector" indx="0">
									<Values>
									<DValue type="img_chnl" value="Aspect_sectors_N0" scope="" indx="0"></DValue>
									<DValue value="1." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="1">
									<Values>
									<DValue type="img_chnl" value="Aspect_sectors_Nmax" scope="" indx="0"></DValue>
									<DValue value="1." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="2">
									<Values>
									<DValue type="img_chnl" value="Curv_plan" scope="" indx="0"></DValue>
									<DValue value="2." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="3">
									<Values>
									<DValue type="img_chnl" value="Curv_profile" scope="" indx="0"></DValue>
									<DValue value="2." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									</Values>
									</DValue>
									<DValue type="vector" name="vImgLayerWght">
									<Values>
									<DValue type="vector" indx="0">
									<Values>
									<DValue type="img_chnl" value="Aspect_sectors_N0" scope="" indx="0"></DValue>
									<DValue value="1." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="1">
									<Values>
									<DValue type="img_chnl" value="Aspect_sectors_Nmax" scope="" indx="0"></DValue>
									<DValue value="1." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="2">
									<Values>
									<DValue type="img_chnl" value="Curv_plan" scope="" indx="0"></DValue>
									<DValue value="2." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="3">
									<Values>
									<DValue type="img_chnl" value="Curv_profile" scope="" indx="0"></DValue>
									<DValue value="2." type="double" indx="1"></DValue>
									</Values>
									</DValue>
									</Values>
									</DValue>
									<DValue type="vector" name="vThmLayers">
									<Values></Values>
									</DValue>
									<DValue value="{val_scale:0.1f}" type="double" name="vrblValScale"></DValue>
									<DValue value="0.59999999999999997779553950749686919153" type="double" name="vrblHCShape"></DValue>
									<DValue value="1." type="double" name="vrblHCArea"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="{input_layer}" bVrbl="0">
									<Assignment MapLvl="1" MapName="main"></Assignment>
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="3" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="3" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="7D5D60D1-C310-48dc-9D5D-65BAAA4062F5" InstID="Length/Width"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="3." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="4B11667E-1449-440f-8D7B-0A4D90E62B3E" InstID="Standard deviation DEM"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="30." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									</TermGroup>
									</TermThrsh>
									</DValue>
									<DValue type="threshold" name="valThrsh2"></DValue>
									<DValue value="From Parent" type="string" name="valMap"></DValue>
									<DValue value="From Parent" type="string" name="valROI"></DValue>
									<DValue value="0" type="int" name="iNumMaxObj"></DValue>
									<DValue value="4" type="int" name="iVersion"></DValue>
									<DValue value="-1" type="int" name="iOldLvl"></DValue>
									<DValue value="0" type="int" name="iOldDsplLvl"></DValue>
									<DValue value="0" type="int" name="iOldDsplNumLvl"></DValue>
								</Params>
							</Domain>
							<SubProc></SubProc>
						</ProcBase>
						<ProcBase Name="with Existence of super objects release (1) = 1  at  {output_layer}: release" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="3AC44F21-C6B2-4804-9929-BB18BE6F2051">
								<Params>
									<DValue value="3" type="clssId" name="valClass"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="{output_layer}" bVrbl="0">
									<Assignment MapLvl="2" MapName="main"></Assignment>
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Disabled" type="string" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="5" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="7F30AE70-0DDD-483c-A693-7698C3CB96FF" InstID="Existence of super objects release (1)"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="1." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									</TermGroup>
									</TermThrsh>
									</DValue>
									<DValue type="threshold" name="valThrsh2"></DValue>
									<DValue value="From Parent" type="string" name="valMap"></DValue>
									<DValue value="From Parent" type="string" name="valROI"></DValue>
									<DValue value="0" type="int" name="iNumMaxObj"></DValue>
									<DValue value="4" type="int" name="iVersion"></DValue>
									<DValue value="-1" type="int" name="iOldLvl"></DValue>
									<DValue value="0" type="int" name="iOldDsplLvl"></DValue>
									<DValue value="0" type="int" name="iOldDsplNumLvl"></DValue>
								</Params>
							</Domain>
							<SubProc></SubProc>
						</ProcBase>
<!-- END split_long_polygons.tpl input_layer={input_layer}, output_layer={output_layer}, val_scale={val_scale} -->
