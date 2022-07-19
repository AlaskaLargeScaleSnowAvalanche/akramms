<?xml version="1.0" encoding="UTF-8"?>
<eCog.Proc UserName="buehlery" Company="" Copyright="" version="20181002" use-reproducable-poly="1" project-unit="5" engine-version="10.1.0" engine-build="4429" update-topology="0" distance_calculation="CG" resampling_compatibility="0" ver="0">
	<ruleset-info>
		<name></name>
		<author>buehlery</author>
		<tags></tags>
		<version></version>
		<description></description>
		<input></input>
		<output></output>
	</ruleset-info>
	<ParamValueSetCntnr></ParamValueSetCntnr>
	<ObjectDependencies>
		<ImgLayers>
			<ChnlProxyCntnr>
				<Layers>
					<ChnlProxy strName="Aspect_sectors_N0" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="Aspect_sectors_Nmax" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="Curv_plan" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="Curv_profile" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="DEM" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="Slope" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
					<ChnlProxy strName="PRA_raw" flags="12">
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					</ChnlProxy>
				</Layers>
				<Variables></Variables>
			</ChnlProxyCntnr>
		</ImgLayers>
		<ThmLayers>
			<ChnlProxyCntnr>
				<Layers></Layers>
				<Variables></Variables>
			</ChnlProxyCntnr>
		</ThmLayers>
		<MapLvlProxyCntnr>
			<MapLvlProxies>
				<MapLvlProxy strName="L fine" bVrbl="0">
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
				</MapLvlProxy>
				<MapLvlProxy strName="L pixel" bVrbl="0">
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
				</MapLvlProxy>
{map_level_proxys}
			</MapLvlProxies>
			<MapLvlVrblValues></MapLvlVrblValues>
		</MapLvlProxyCntnr>
		<ProcVrblCntnr></ProcVrblCntnr>
		<ClssHrchy EvalInvalid="1" MinProb="0.10000000000000000555111512312578270212" NNSlope="0.20000000000000001110223024625156540424" RdiResamplOptns="3">
			<AllClss>
				<Clss id="1" name="steep" flag="0" iMaskID="-1" bUsePrntClr="0" dPrntClssBrghtns="0." termType="0" strUserName="buehlery" tChngTime="1495177121" bShow="0" Trans="0.">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					<Color R="189" G="0" B="0"></Color>
					<SharedInfo bShared="0" strInstGUID=""></SharedInfo>
				</Clss>
				<Clss id="2" name="flat" flag="0" iMaskID="-1" bUsePrntClr="0" dPrntClssBrghtns="0." termType="0" strUserName="buehlery" tChngTime="1495177127" bShow="0" Trans="0.">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					<Color R="0" G="128" B="0"></Color>
					<SharedInfo bShared="0" strInstGUID=""></SharedInfo>
				</Clss>
				<Clss id="3" name="release" flag="2" iMaskID="-1" bUsePrntClr="0" dPrntClssBrghtns="0." termType="0" strUserName="buehlery" tChngTime="1495178196" bShow="0" Trans="0.">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					<Color R="255" G="0" B="0"></Color>
					<SharedInfo bShared="0" strInstGUID=""></SharedInfo>
				</Clss>
				<Clss id="4" name="long_large" flag="0" iMaskID="-1" bUsePrntClr="0" dPrntClssBrghtns="0." termType="0" strUserName="buehlery" tChngTime="1575941224" bShow="0" Trans="0.">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
					<Color R="0" G="0" B="255"></Color>
					<SharedInfo bShared="0" strInstGUID=""></SharedInfo>
				</Clss>
			</AllClss>
			<PropTree version="20100426">
				<AllProps>
					<PropDscr Flag="65538" strUserName="vonricken" tChngTime="1523453895" group_id="ext.geom.object.prop">
						<PropDscrId GUID="F4CD2EB0-F2FB-47fb-89A3-369FE9B58085" InstID="Border length"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<DUnitInfo Conversion="0" UnitType="1" Dim="1"></DUnitInfo>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="65538" strUserName="buehlery" tChngTime="1495176807" group_id="ext.geom.object.prop">
						<PropDscrId GUID="03E04ED0-94DD-45ee-801E-14D70E6E2417" InstID="Area"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<DUnitInfo Conversion="0" UnitType="1" Dim="2"></DUnitInfo>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="16777218" strUserName="vonricken" tChngTime="1523548399" group_id="object.cust.prop">
						<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="ratio_area_borderlength"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="_ratio_area_borderlength" type="string" name="NameExpr"></DValue>
							<DValue type="vector" name="valPropVctr">
								<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="03E04ED0-94DD-45ee-801E-14D70E6E2417" InstID="Area"></PropDscrId>
									</DValue>
									<DValue type="propDscrId" indx="1">
									<PropDscrId GUID="F4CD2EB0-F2FB-47fb-89A3-369FE9B58085" InstID="Border length"></PropDscrId>
									</DValue>
								</Values>
							</DValue>
							<DValue value="d00;/d01;" type="string" name="strExpr"></DValue>
							<DValue value="0" type="int" name="iUnit"></DValue>
							<DValue value="" type="string" name="Comment"></DValue>
							<DValue value="1" type="bool" name="bUseDeg"></DValue>
							<DValue value="0" type="bool" name="bUseUnit"></DValue>
							<DValue value="0" type="bool" name="bShared"></DValue>
							<DValue value="" type="string" name="strInstGUID"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2147483648" strUserName="buehlery" tChngTime="1495176807" group_id="map.map.prop">
						<PropDscrId GUID="008E6DF8-7DE7-49df-9CA1-703BC73B5C37" InstID="Scene resolution (coor. unit)"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="16777218" strUserName="buehlery" tChngTime="1495177527" group_id="object.cust.prop">
						<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="_area m2" type="string" name="NameExpr"></DValue>
							<DValue type="vector" name="valPropVctr">
								<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="03E04ED0-94DD-45ee-801E-14D70E6E2417" InstID="Area"></PropDscrId>
									</DValue>
									<DValue type="propDscrId" indx="1">
									<PropDscrId GUID="008E6DF8-7DE7-49df-9CA1-703BC73B5C37" InstID="Scene resolution (coor. unit)"></PropDscrId>
									</DValue>
								</Values>
							</DValue>
							<DValue value="d00;*(d01;^2)" type="string" name="strExpr"></DValue>
							<DValue value="0" type="int" name="iUnit"></DValue>
							<DValue value="" type="string" name="Comment"></DValue>
							<DValue value="1" type="bool" name="bUseDeg"></DValue>
							<DValue value="0" type="bool" name="bUseUnit"></DValue>
							<DValue value="0" type="bool" name="bShared"></DValue>
							<DValue value="" type="string" name="strInstGUID"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="wksp.scene.global.prop">
						<PropDscrId GUID="E2027F03-6D7A-43f3-BF08-50075CB38528" InstID="Second level scene name"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528461882" group_id="ext.geom.object.prop">
						<PropDscrId GUID="DEA2DCB1-BD89-4972-971A-65C1F58FA3C0" InstID="Width"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<DUnitInfo Conversion="0" UnitType="1" Dim="1"></DUnitInfo>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="65538" strUserName="buehlery" tChngTime="1495176807" group_id="ext.geom.object.prop">
						<PropDscrId GUID="AF0D7167-ADE8-4240-AAA4-AC2C188E9AF5" InstID="Number of pixels"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1495783102" group_id="relbrdr.nghb.objrel.object.prop">
						<PropDscrId GUID="AA7CAC99-696D-4983-8F48-D07C4F816F2C" InstID="Rel. border to release"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="3" type="clssId" name="valClss"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="65538" strUserName="vonricken" tChngTime="1528461882" group_id="ext.geom.object.prop">
						<PropDscrId GUID="91CC47C7-93D6-4829-A54F-44E87267F342" InstID="Length"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<DUnitInfo Conversion="0" UnitType="1" Dim="1"></DUnitInfo>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="misc.global.prop">
						<PropDscrId GUID="80EFE1D1-67E1-4740-A324-7F2C30971B68" InstID="Workspace full path"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1495806089" group_id="exist.super.objrel.object.prop">
						<PropDscrId GUID="7F30AE70-0DDD-483c-A693-7698C3CB96FF" InstID="Existence of super objects release (1)"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="3" type="clssId" name="valClss"></DValue>
							<DValue value="1" type="int" name="iDist"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1575943990" group_id="exist.super.objrel.object.prop">
						<PropDscrId GUID="7F30AE70-0DDD-483c-A693-7698C3CB96FF" InstID="Existence of super objects long (1)"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="4" type="clssId" name="valClss"></DValue>
							<DValue value="1" type="int" name="iDist"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1535470648" group_id="meandiff.nghb.objrel.object.prop">
						<PropDscrId GUID="7EA25A92-BF40-4531-96F2-1FFD62A8F45C" InstID="Mean diff. to Aspect_sectors_N0, release"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue value="3" type="clssId" name="valClss"></DValue>
							<DValue type="img_chnl" value="Aspect_sectors_N0" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528461882" group_id="ext.geom.object.prop">
						<PropDscrId GUID="7D5D60D1-C310-48dc-9D5D-65BAAA4062F5" InstID="Length/Width"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="misc.global.prop">
						<PropDscrId GUID="7A26EA70-A545-4A12-8BD1-6C09EB200D7F" InstID="Image directory"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="scene.global.prop">
						<PropDscrId GUID="5A2206BC-4452-4E80-97E1-5B5881029833" InstID="Image name"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1580388910" group_id="stdev.chnl.object.prop">
						<PropDscrId GUID="4B11667E-1449-440f-8D7B-0A4D90E62B3E" InstID="Standard deviation DEM"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="DEM" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528881663" group_id="mean.chnl.object.prop">
						<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean Aspect_sectors_N0"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="Aspect_sectors_N0" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528881663" group_id="mean.chnl.object.prop">
						<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean Aspect_sectors_Nmax"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="Aspect_sectors_Nmax" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528798796" group_id="mean.chnl.object.prop">
						<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="PRA_raw" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1495176979" group_id="mean.chnl.object.prop">
						<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean Slope"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="Slope" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="buehlery" tChngTime="1535707846" group_id="mean.chnl.object.prop">
						<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean DEM"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params>
							<DValue type="img_chnl" value="DEM" scope="" name="valChnl"></DValue>
						</Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1534489376" group_id="shape.geom.object.prop">
						<PropDscrId GUID="40CC7324-96B4-409c-B786-B184C1259197" InstID="Shape index"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="misc.global.prop">
						<PropDscrId GUID="31DDEACA-738E-4311-84FF-9A0733418D63" InstID="Image full path"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2" strUserName="vonricken" tChngTime="1528461882" group_id="shape.geom.object.prop">
						<PropDscrId GUID="1F03F8EB-A21A-4d53-B9DA-391FFE1B804D" InstID="Compactness"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
					<PropDscr Flag="2147483650" strUserName="vonricken" tChngTime="1535976446" group_id="scene.global.prop">
						<PropDscrId GUID="1A5A8116-70E0-46ce-8BD7-D9B0973727AA" InstID="Scene name"></PropDscrId>
						<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
						<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
						<Params></Params>
					</PropDscr>
				</AllProps>
				<UserGroups></UserGroups>
			</PropTree>
			<Brightness>
				<Map MapName="main">
					<ChnlWghtBrght>
						<BrghtWght val="0." chnl="0"></BrghtWght>
						<BrghtWght val="0." chnl="1"></BrghtWght>
						<BrghtWght val="0." chnl="2"></BrghtWght>
						<BrghtWght val="0." chnl="3"></BrghtWght>
						<BrghtWght val="1." chnl="4"></BrghtWght>
						<BrghtWght val="1." chnl="5"></BrghtWght>
						<BrghtWght val="1." chnl="6"></BrghtWght>
						<BrghtWght val="1." chnl="7"></BrghtWght>
					</ChnlWghtBrght>
				</Map>
			</Brightness>
			<AllVrblClss></AllVrblClss>
			<AllSubClss>
				<Clss Id="1" PrfdGrp="1">
					<SubClss></SubClss>
					<SubGrp></SubGrp>
				</Clss>
				<Clss Id="2" PrfdGrp="2">
					<SubClss></SubClss>
					<SubGrp></SubGrp>
				</Clss>
				<Clss Id="3" PrfdGrp="3">
					<SubClss></SubClss>
					<SubGrp></SubGrp>
				</Clss>
				<Clss Id="4" PrfdGrp="4">
					<SubClss></SubClss>
					<SubGrp></SubGrp>
				</Clss>
			</AllSubClss>
			<AllTerm>
				<Term TermEvalType="0">
					<TermBase ClssId="1" flags="0">
						<Weight>
							<DValue value="1" type="int"></DValue>
						</Weight>
					</TermBase>
				</Term>
				<Term TermEvalType="0">
					<TermBase ClssId="2" flags="0">
						<Weight>
							<DValue value="1" type="int"></DValue>
						</Weight>
					</TermBase>
				</Term>
				<Term TermEvalType="0">
					<TermBase ClssId="3" flags="0">
						<Weight>
							<DValue value="1" type="int"></DValue>
						</Weight>
					</TermBase>
				</Term>
				<Term TermEvalType="0">
					<TermBase ClssId="4" flags="0">
						<Weight>
							<DValue value="1" type="int"></DValue>
						</Weight>
					</TermBase>
				</Term>
			</AllTerm>
		</ClssHrchy>
		<MapVrblCntnr></MapVrblCntnr>
		<FtrListVrblCntnr></FtrListVrblCntnr>
		<CoordVrblCntnr></CoordVrblCntnr>
		<ROIVrblCntnr></ROIVrblCntnr>
		<ImgObjListVrblCntnr></ImgObjListVrblCntnr>
		<ArrayCntnr>
			<Arrays></Arrays>
			<ArrayVrbls></ArrayVrbls>
		</ArrayCntnr>
		<Smpls>
			<AllClss>
				<SmplList ClssId="1"></SmplList>
				<SmplList ClssId="2"></SmplList>
				<SmplList ClssId="3"></SmplList>
				<SmplList ClssId="4"></SmplList>
			</AllClss>
			<AllProp></AllProp>
		</Smpls>
		<plugin-list>
			<plugin name="eCognition Internal Export Process Algorithms" version="0.1"></plugin>
			<plugin name="eCognition Internal Process Algorithms" version="0.1"></plugin>
			<plugin name="eCognition Basic Process Algorithms" version="0.1"></plugin>
		</plugin-list>
	</ObjectDependencies>
	<CustProcAlgrList></CustProcAlgrList>
	<ExternalCustProcAlgrList></ExternalCustProcAlgrList>
	<ProcessList>
		<ProcBase Name="Process tree {return_period:d}y{_For}" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
			<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
			<vrblValMaxCycle>
				<DValue value="1." type="double"></DValue>
			</vrblValMaxCycle>
			<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
				<Params></Params>
			</Algorithm>
			<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
				<Params>
					<DValue type="threshold" name="valThrsh"></DValue>
					<DValue type="threshold" name="valThrsh2"></DValue>
					<DValue value="From Parent" type="string" name="valMap"></DValue>
				</Params>
			</Domain>
			<SubProc>
				<ProcBase Name="segmentation 1" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
						<ProcBase Name="quadtree: 50 creating 'L pixel'" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="C092C8B6-03A8-42c1-9C21-7A861FD0925C">
								<Params>
									<DValue value="0" type="int" name="iQTMode"></DValue>
									<DValue value="50." type="double" name="vrblQTScale"></DValue>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue value="1" type="bool" name="bDoOverwrite"></DValue>
									<DValue type="vector" name="vImgLayers">
									<Values>
									<DValue type="img_chnl" value="PRA_raw" scope="" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" name="vThmLayers">
									<Values></Values>
									</DValue>
								</Params>
							</Algorithm>
							<Domain guid="682A3AA1-9F4F-4dae-9E44-5015DF867712">
								<Params>
									<DValue type="threshold" name="valThrsh"></DValue>
									<DValue type="threshold" name="valThrsh2"></DValue>
									<DValue value="From Parent" type="string" name="valMap"></DValue>
								</Params>
							</Domain>
							<SubProc></SubProc>
						</ProcBase>
						<ProcBase Name="unclassified with Mean PRA_raw = 200  at  L pixel: merge region" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="2328636B-BAD3-4f5d-B5AA-FC209A0BFB65">
								<Params>
									<DValue value="0" type="bool" name="bFsnUp"></DValue>
									<DValue type="vector" name="vThmLayers">
									<Values></Values>
									</DValue>
									<DValue value="2" type="int" name="iMode"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="5" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="unclassified with Mean PRA_raw &lt; 200  at  L pixel: merge region" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="2328636B-BAD3-4f5d-B5AA-FC209A0BFB65">
								<Params>
									<DValue value="0" type="bool" name="bFsnUp"></DValue>
									<DValue type="vector" name="vThmLayers">
									<Values></Values>
									</DValue>
									<DValue value="2" type="int" name="iMode"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="unclassified with Mean PRA_raw > 200  at  L pixel: merge region" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="2328636B-BAD3-4f5d-B5AA-FC209A0BFB65">
								<Params>
									<DValue value="0" type="bool" name="bFsnUp"></DValue>
									<DValue type="vector" name="vThmLayers">
									<Values></Values>
									</DValue>
									<DValue value="2" type="int" name="iMode"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="3" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
					</SubProc>
				</ProcBase>
				<ProcBase Name="classification 1" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
						<ProcBase Name="unclassified with Mean PRA_raw = 200  at  L pixel: steep" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="3AC44F21-C6B2-4804-9929-BB18BE6F2051">
								<Params>
									<DValue value="1" type="clssId" name="valClass"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="5" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="unclassified with Mean PRA_raw &lt; 200  at  L pixel: flat" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="3AC44F21-C6B2-4804-9929-BB18BE6F2051">
								<Params>
									<DValue value="2" type="clssId" name="valClass"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="unclassified with Mean PRA_raw > 200  at  L pixel: flat" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="3AC44F21-C6B2-4804-9929-BB18BE6F2051">
								<Params>
									<DValue value="2" type="clssId" name="valClass"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="3" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="steep with area m2 &lt; 1000  at  L pixel: remove objects into flat (merge by shape)" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="47D33362-BDFB-4750-8755-11E545062EE8">
								<Params>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="2" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue value="0" type="bool" name="bShowAdv"></DValue>
									<DValue value="0" type="int" name="eMode"></DValue>
									<DValue type="vector" name="vImgLayers">
									<Values></Values>
									</DValue>
									<DValue value="0" type="bool" name="bUseThrsh"></DValue>
									<DValue value="20." type="double" name="vrblThrshColor"></DValue>
									<DValue value="0.20000000000000001110223024625156540424" type="double" name="vrblThrshBrdr"></DValue>
									<DValue value="0" type="bool" name="bUseLgcyPrnt"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="1" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="1000." type="double"></DValue>
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
					</SubProc>
				</ProcBase>
				<ProcBase Name="segementation 2" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
						<ProcBase Name="steep at  L pixel: multi-resolution: {segmentation2_scale:d} [shape:0.6 compct.:1.0] creating 'L fine'" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="6534F2E1-485B-406f-B990-350824399FA8">
								<Params>
									<DValue value="1" type="bool" name="bDoOverwrite"></DValue>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L fine" bVrbl="0">
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
									<DValue value="{segmentation2_scale:0.1f}" type="double" name="vrblValScale"></DValue>
									<DValue value="0.59999999999999997779553950749686919153" type="double" name="vrblHCShape"></DValue>
									<DValue value="1." type="double" name="vrblHCArea"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="1" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh"></DValue>
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
					</SubProc>
				</ProcBase>
				<ProcBase Name="generalization" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
						<ProcBase Name="delete 'L pixel'" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="4D72CCF3-EB44-4dcb-B5E1-70CA007D50CE">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L pixel" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
								</Params>
							</Algorithm>
							<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
								<Params>
									<DValue type="threshold" name="valThrsh"></DValue>
									<DValue type="threshold" name="valThrsh2"></DValue>
									<DValue value="From Parent" type="string" name="valMap"></DValue>
								</Params>
							</Domain>
							<SubProc></SubProc>
						</ProcBase>
						<ProcBase Name="unclassified with Mean PRA_raw = 200  at  L fine: release" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
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
									<MapLvlProxy strName="L fine" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="5" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean PRA_raw"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="200." type="double"></DValue>
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
						<ProcBase Name="release at  L fine: grow into all where rel. area of object pixels in (3 x 3) >=0.5" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="26A5FE32-0E27-4c1d-823D-3F2B3CA9712A">
								<Params>
									<DValue value="0" type="int" name="eMode"></DValue>
									<DValue value="-1" type="clssId" name="pTargetClass"></DValue>
									<DValue value="1" type="bool" name="bGnrlConnectedOnly"></DValue>
									<DValue value="3" type="int" name="eGrowInX"></DValue>
									<DValue value="3" type="int" name="eGrowInY"></DValue>
									<DValue value="0" type="bool" name="bBalanceDir"></DValue>
									<DValue type="vector" name="mCandClass">
									<Values>
									<DValue value="Disabled" type="string" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="mCandCond"></DValue>
									<DValue type="img_chnl" value="" name="pLayer1"></DValue>
									<DValue value="4" type="int" name="eLayer1Cmp"></DValue>
									<DValue value="1" type="bool" name="bLayer1AbsTrsh"></DValue>
									<DValue value="0" type="int" name="mLayer1Value"></DValue>
									<DValue value="0" type="int" name="mLayer1Tolerance"></DValue>
									<DValue value="0" type="int" name="eTol1"></DValue>
									<DValue type="img_chnl" value="" name="pLayer2"></DValue>
									<DValue value="4" type="int" name="eLayer2Cmp"></DValue>
									<DValue value="1" type="bool" name="bLayer2AbsTrsh"></DValue>
									<DValue value="0" type="int" name="mLayer2Value"></DValue>
									<DValue value="0" type="int" name="mLayer2Tolerance"></DValue>
									<DValue value="0" type="int" name="eTol2"></DValue>
									<DValue value="1" type="int" name="eDstSurfMode"></DValue>
									<DValue type="vector" name="mDstSurfClass">
									<Values>
									<DValue value="Disabled" type="string" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue value="4" type="int" name="eDstSurfCmp"></DValue>
									<DValue value="0.5" type="double" name="mDstSurfValue"></DValue>
									<DValue value="3" type="int" name="mDstSurfBox"></DValue>
									<DValue value="1" type="int" name="mDstSurfBoxZ"></DValue>
									<DValue value="-1" type="procVarId" name="mMinObjSize"></DValue>
									<DValue value="-1" type="procVarId" name="mMaxObjSize"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L fine" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="3" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh"></DValue>
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
						<ProcBase Name="release at  L fine: shrink using unclassified where rel. area of object pixels in (3 x 3) &lt;=0.5" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="26A5FE32-0E27-4c1d-823D-3F2B3CA9712A">
								<Params>
									<DValue value="1" type="int" name="eMode"></DValue>
									<DValue value="-1" type="clssId" name="pTargetClass"></DValue>
									<DValue value="1" type="bool" name="bGnrlConnectedOnly"></DValue>
									<DValue value="3" type="int" name="eGrowInX"></DValue>
									<DValue value="3" type="int" name="eGrowInY"></DValue>
									<DValue value="0" type="bool" name="bBalanceDir"></DValue>
									<DValue type="vector" name="mCandClass">
									<Values>
									<DValue value="Disabled" type="string" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="mCandCond"></DValue>
									<DValue type="img_chnl" value="" name="pLayer1"></DValue>
									<DValue value="4" type="int" name="eLayer1Cmp"></DValue>
									<DValue value="1" type="bool" name="bLayer1AbsTrsh"></DValue>
									<DValue value="0" type="int" name="mLayer1Value"></DValue>
									<DValue value="0" type="int" name="mLayer1Tolerance"></DValue>
									<DValue value="0" type="int" name="eTol1"></DValue>
									<DValue type="img_chnl" value="" name="pLayer2"></DValue>
									<DValue value="4" type="int" name="eLayer2Cmp"></DValue>
									<DValue value="1" type="bool" name="bLayer2AbsTrsh"></DValue>
									<DValue value="0" type="int" name="mLayer2Value"></DValue>
									<DValue value="0" type="int" name="mLayer2Tolerance"></DValue>
									<DValue value="0" type="int" name="eTol2"></DValue>
									<DValue value="1" type="int" name="eDstSurfMode"></DValue>
									<DValue type="vector" name="mDstSurfClass">
									<Values>
									<DValue value="Disabled" type="string" indx="0"></DValue>
									</Values>
									</DValue>
									<DValue value="1" type="int" name="eDstSurfCmp"></DValue>
									<DValue value="0.5" type="double" name="mDstSurfValue"></DValue>
									<DValue value="3" type="int" name="mDstSurfBox"></DValue>
									<DValue value="1" type="int" name="mDstSurfBoxZ"></DValue>
									<DValue value="-1" type="procVarId" name="mMinObjSize"></DValue>
									<DValue value="-1" type="procVarId" name="mMaxObjSize"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L fine" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="3" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh"></DValue>
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
						<ProcBase Name="release with area m2 &lt; 500  and Mean diff. to Aspect_sectors_N0, release &lt; 75  and Mean diff. to Aspect_sectors_N0, release > -75  at  L fine: remove objects into release (merge by shape)" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="47D33362-BDFB-4750-8755-11E545062EE8">
								<Params>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="3" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue value="0" type="bool" name="bShowAdv"></DValue>
									<DValue value="0" type="int" name="eMode"></DValue>
									<DValue type="vector" name="vImgLayers">
									<Values></Values>
									</DValue>
									<DValue value="0" type="bool" name="bUseThrsh"></DValue>
									<DValue value="20." type="double" name="vrblThrshColor"></DValue>
									<DValue value="0.20000000000000001110223024625156540424" type="double" name="vrblThrshBrdr"></DValue>
									<DValue value="0" type="bool" name="bUseLgcyPrnt"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L fine" bVrbl="0">
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
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="500." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="2" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="7EA25A92-BF40-4531-96F2-1FFD62A8F45C" InstID="Mean diff. to Aspect_sectors_N0, release"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="75." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="3" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="7EA25A92-BF40-4531-96F2-1FFD62A8F45C" InstID="Mean diff. to Aspect_sectors_N0, release"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="-75." type="double"></DValue>
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
						<ProcBase Name="unclassified with area m2 &lt;= 250  and Rel. border to release >= 0.75  at  L fine: remove objects into release (merge by shape)" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="47D33362-BDFB-4750-8755-11E545062EE8">
								<Params>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="3" type="clssId" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue value="0" type="bool" name="bShowAdv"></DValue>
									<DValue value="0" type="int" name="eMode"></DValue>
									<DValue type="vector" name="vImgLayers">
									<Values></Values>
									</DValue>
									<DValue value="0" type="bool" name="bUseThrsh"></DValue>
									<DValue value="20." type="double" name="vrblThrshColor"></DValue>
									<DValue value="0.20000000000000001110223024625156540424" type="double" name="vrblThrshBrdr"></DValue>
									<DValue value="0" type="bool" name="bUseLgcyPrnt"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="L fine" bVrbl="0">
									<Scope GUID="00000000-0000-0000-0000-000000000000"></Scope>
									</MapLvlProxy>
									</DValue>
									<DValue type="vector" name="mClssFltr">
									<Values>
									<DValue value="Unclsfy" type="string" indx="0"></DValue>
									<DValue value="User defined" type="string" indx="1"></DValue>
									</Values>
									</DValue>
									<DValue type="threshold" name="valThrsh">
									<TermThrsh>
									<TermGroup eJoint="2">
									<TermCondition eCmpr="1" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="250." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="4" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="AA7CAC99-696D-4983-8F48-D07C4F816F2C" InstID="Rel. border to release"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="0.75" type="double"></DValue>
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
					</SubProc>
				</ProcBase>
				<ProcBase Name="Split long Polygons" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
{split_long_polygonss}
					</SubProc>
				</ProcBase>
				<ProcBase Name="export I frequent" bLoopChg="0" bExpand="1" bActive="1" bAutoName="0" bSubrtn="0">
					<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
					<vrblValMaxCycle>
						<DValue value="1." type="double"></DValue>
					</vrblValMaxCycle>
					<Algorithm guid="A8BA5775-CC39-4194-9A6A-A64872EE1F81">
						<Params></Params>
					</Algorithm>
					<Domain guid="CC9F2C30-4DB0-4ef2-B864-63560D1D6BF3">
						<Params>
							<DValue type="threshold" name="valThrsh"></DValue>
							<DValue type="threshold" name="valThrsh2"></DValue>
							<DValue value="From Parent" type="string" name="valMap"></DValue>
						</Params>
					</Domain>
					<SubProc>
						<ProcBase Name="release with area m2 >= 500  and Mean Slope >= {min_mean_slope:d}  and Mean DEM >= {min_pra_elevation}  at  "{split_long_polygonss_output_layer}: export object shapes to variable" bLoopChg="0" bExpand="1" bActive="1" bAutoName="1" bSubrtn="0">
							<LcnsInfo sLcnsId="" sPwd=""></LcnsInfo>
							<vrblValMaxCycle>
								<DValue value="1." type="double"></DValue>
							</vrblValMaxCycle>
							<Algorithm guid="E8AAA2C4-4DCA-4684-A918-87E7C53CDC8D">
								<Params>
									<DValue value="2" type="int" name="eExportMode"></DValue>
									<DValue value="ObjectShapes001" type="string" name="strExportItem"></DValue>
									<DValue value="-1" type="procVarId" name="vrblExportItem"></DValue>
									<DValue value="{scene_dir}/PRA_{return_period_category}/PRA_{return_period:d}y{_For}.xml" type="string" name="strExportPath"></DValue>
									<DValue value="0" type="bool" name="bExportSeries"></DValue>
									<DValue value="&lt;?xml version=&quot;1.0&quot; encoding=&quot;UTF-8&quot;?>&#xA;&lt;ExportInfo SingleFilePerWksp=&quot;0&quot; SingleFilePerItem=&quot;1&quot; ExportItem=&quot;ExportList&quot; ExportType=&quot;ExpList&quot; DriverID=&quot;ELS&quot; ExportPath=&quot;{scene_dir}/PRA_{return_period_category}/PRA_{return_period:d}y{_For}.xml&quot;>&lt;/ExportInfo>" type="string" name="strExportItemInfo"></DValue>
									<DValue value="temporary" type="string" name="valExportTempLayer"></DValue>
									<DValue type="vector" name="vColInfo">
									<Values>
									<DValue type="vector" indx="0">
									<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
									</DValue>
									<DValue value="area_m2" type="string" indx="1"></DValue>
									<DValue value="2" type="int" indx="2"></DValue>
									<DValue value="-1" type="int" indx="3"></DValue>
									<DValue value="-1" type="int" indx="4"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="1">
									<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean DEM"></PropDscrId>
									</DValue>
									<DValue value="Mean_DEM" type="string" indx="1"></DValue>
									<DValue value="2" type="int" indx="2"></DValue>
									<DValue value="-1" type="int" indx="3"></DValue>
									<DValue value="-1" type="int" indx="4"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="2">
									<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean Slope"></PropDscrId>
									</DValue>
									<DValue value="Mean_Slope" type="string" indx="1"></DValue>
									<DValue value="2" type="int" indx="2"></DValue>
									<DValue value="-1" type="int" indx="3"></DValue>
									<DValue value="-1" type="int" indx="4"></DValue>
									</Values>
									</DValue>
									<DValue type="vector" indx="3">
									<Values>
									<DValue type="propDscrId" indx="0">
									<PropDscrId GUID="008E6DF8-7DE7-49df-9CA1-703BC73B5C37" InstID="Scene resolution (coor. unit)"></PropDscrId>
									</DValue>
									<DValue value="Scene_reso" type="string" indx="1"></DValue>
									<DValue value="2" type="int" indx="2"></DValue>
									<DValue value="-1" type="int" indx="3"></DValue>
									<DValue value="-1" type="int" indx="4"></DValue>
									</Values>
									</DValue>
									</Values>
									</DValue>
									<DValue value="0" type="bool" name="bUseFtrList"></DValue>
									<DValue value="area_m2; Mean_DEM; Mean_Slope; Scene_reso" type="string" name="EditAttrTbl"></DValue>
									<DValue value="-1" type="procVarId" name="FeatureListAttrTbl"></DValue>
									<DValue value="3" type="int" name="eGeomType"></DValue>
									<DValue value="8" type="int" name="eExprtType"></DValue>
									<DValue value="1" type="bool" name="bShpUseGeocoding"></DValue>
									<DValue value="0" type="int" name="eCoordOrient"></DValue>
									<DValue value="SHP" type="string" name="eExprtFormat"></DValue>
									<DValue value="ObjectShapes" type="string" name="featClassName"></DValue>
									<DValue type="img_chnl" value="" name="pRefChnl"></DValue>
									<DValue value="{LEFT_BRACKET}:ArcSDE.Connect.Dir{RIGHT_BRACKET}/default.das" type="string" name="exprtStorageLocFile"></DValue>
									<DValue value="2000000,1000000" type="string" name="spatDomainOffset"></DValue>
									<DValue value="1000" type="string" name="spatDomainPrec"></DValue>
								</Params>
							</Algorithm>
							<Domain guid="CED621BD-F4D1-4ffa-A2F6-DB2BB1913E8C">
								<Params>
									<DValue type="lvlName" name="valMapLvl">
									<MapLvlProxy strName="{split_long_polygonss_output_layer}" bVrbl="0">
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
									<TermCondition eCmpr="4" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="E869FC89-440F-41e4-A7DF-1E9DE9040CEC" InstID="area m2"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="500." type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="4" eBaseUnit="0" eJoint="0">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean Slope"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="{min_mean_slope:0.1f}" type="double"></DValue>
									</ProcVrblVal2>
									</TermCondition>
									<TermCondition eCmpr="4" eBaseUnit="0" eJoint="2">
									<ProcVrblVal1>
									<DValue type="propDscrId">
									<PropDscrId GUID="44411C83-609B-4758-93D3-FF62DF246855" InstID="Mean DEM"></PropDscrId>
									</DValue>
									</ProcVrblVal1>
									<ProcVrblVal2>
									<DValue value="{min_pra_elevation}" type="double"></DValue>
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
					</SubProc>
				</ProcBase>
			</SubProc>
		</ProcBase>
	</ProcessList>
	<ExportedItems>
		<item name="ExportList" type="ExpList" driver="ELS" ext="xml" path="{scene_dir}/PRA_{return_period_category}/PRA_{return_period:d}y{_For}.xml"></item>
	</ExportedItems>
	<LcnsIds></LcnsIds>
</eCog.Proc>
