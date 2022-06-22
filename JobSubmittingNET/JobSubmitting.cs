using System;
using System.IO;
using JobSubmittingNET.DiaJobScheduler;


// a workaround for default KeepAlive option for soap connection, when submitting job keep-alive may block other processes
namespace JobSubmittingNET.DiaJobScheduler
{
    using System;
    using System.Web.Services;
    using System.Diagnostics;
    using System.Web.Services.Protocols;
    using System.ComponentModel;
    using System.Xml.Serialization;

    public partial class DiaJS : System.Web.Services.Protocols.SoapHttpClientProtocol
    {
        protected override System.Net.WebRequest GetWebRequest(Uri uri)
        {
            System.Net.HttpWebRequest webRequest = (System.Net.HttpWebRequest)base.GetWebRequest(uri);
            webRequest.KeepAlive = false; // disable keep alive, for submitting the job this is ot necessary anyhow
            return webRequest;
        }
    }
}


namespace JobSubmittingNET
{
	/// <summary>
	/// Summary description for Class1.
	/// </summary>
	class JobSubmitting
	{
		//---------------------------------------------------------------
		//	Sample data
		//---------------------------------------------------------------
        static string szRullsetPath = "..\\Data\\fastrule.dcp";		// ruleset
        static string szLayer1ImgPath = "..\\Data\\cell1.tif";		// image 1
        static string szLayer2ImgPath = "..\\Data\\cell2.tif";		// image 1
		static string szExpItem1 = "..\\..\\..\\Data\\out.csv";				// output csv file
		static string szExpItem2 = "..\\..\\..\\Data\\out1.dpr";
        static string szExpItem3 = "..\\..\\..\\Data\\out2.dpr";		// image 1
		static string szServer = "http://localhost:8186";					// server url
		static string szGuid = "81B9641D-6671-4979-9224-F1E4AC4AD553";	// job guid

        // optional ruleset arguments - override rule-set information stored in ruleset file
        static string szRulesetParams = 
        "<Args><Ruleset>" + 
	        "<ruleset-info>" + 
		        "<input>" + 
			        "<parameter name=\"param1\" description=\"\" value-type=\"double\">55</parameter>" + 
		        "</input>" + 
		        "<output>" +
                    "<export-item name=\"MyStats1\" enabled=\"true\" output-file-name=\"MyStats1_param\" description=\"output statistical values\">C:\\</export-item>" + 
		        "</output>" +
            "</ruleset-info>" + 
        "</Ruleset></Args>";

		static bool bLocal = true;
		/// <summary>
		/// The main entry point for the application.
		/// </summary>
		[STAThread]
		static void Main(string[] args)
		{
			SubmitJob();
		}

		static void SubmitJob()
		{
			string szRulles;

			//---------------------------------------------------------------
			//	load ruleset
			//---------------------------------------------------------------
			try 
			{
				// Create an instance of StreamReader to read from a file.
				// The using statement also closes the StreamReader.
				StreamReader sr = new StreamReader(szRullsetPath);
				szRulles =  sr.ReadToEnd();
			}
			catch (Exception e) 
			{
				// Let the user know what went wrong.
				Console.WriteLine("The file could not be read:");
				Console.WriteLine(e.Message);
				return;
			}

			//---------------------------------------------------------------
			//	Job creation
			//---------------------------------------------------------------
			UserJob rootjob = new UserJob();

            rootjob.strWkspGUID = new SString();
            rootjob.strWkspName = new SString();
            rootjob.strUserName = new SString();
            rootjob.strRuleSet = new SString();
            rootjob.vJobs = new Job[2];

            rootjob.strWkspGUID.str = szGuid;
            rootjob.strWkspName.str = "test workspace";
            rootjob.strUserName.str = "john";
            rootjob.eOrderType = EOrderType.EParallel;
            rootjob.strRuleSet.str = szRulles;

			//---------------------------------------------------------------
			// add a scene to the job
			//---------------------------------------------------------------
			{
				Job job = CreateScene("test scene 1",2,1);
                job.strProcessArgs = new SString();
                job.strProcessArgs.str = szRulesetParams;

				//---------------------------------------------------------------
				// image layers
				//---------------------------------------------------------------
				//---------------------------------------------------------------
				// image layer 1
				//---------------------------------------------------------------
                job.mScene.vImgLayers[0] = CreateLayer("Layer 1", szLayer1ImgPath);
				//---------------------------------------------------------------
				// image layer 2
				//---------------------------------------------------------------
                job.mScene.vImgLayers[1] = CreateLayer("Layer 2", szLayer1ImgPath);
				//---------------------------------------------------------------
				// export spec
				//---------------------------------------------------------------
                // MyStats1 export is specified by szRulesetParams
                job.mExportSpec[0] = CreateExportItem("ProjectFile", szExpItem2, "DPR", 0);
				//---------------------------------------------------------------
				// add the scene
				//---------------------------------------------------------------
                rootjob.vJobs[0] = job;
			}
			//---------------------------------------------------------------
			// add a scene to the job
			//---------------------------------------------------------------
			{
				Job job2 = CreateScene("test scene 2",2,2);
				//---------------------------------------------------------------
				// image layers
				//---------------------------------------------------------------
				//---------------------------------------------------------------
				// image layer 1
				//---------------------------------------------------------------
                job2.mScene.vImgLayers[0] = CreateLayer("Layer 1", szLayer2ImgPath);

				//---------------------------------------------------------------
				// image layer 2
				//---------------------------------------------------------------
                job2.mScene.vImgLayers[1] = CreateLayer("Layer 2", szLayer2ImgPath);
				//---------------------------------------------------------------
				// export spec
				//---------------------------------------------------------------
                job2.mExportSpec[0] = CreateExportItem("MyStats1", szExpItem1, "CSV", 1);
                job2.mExportSpec[1] = CreateExportItem("ProjectFile", szExpItem3, "DPR", 0);

                rootjob.vJobs[1] = job2;
			}

            rootjob.oCnfg = new JobConfig();
            rootjob.oCnfg.strConfig = new SString();
            rootjob.oCnfg.strConfig.str = "eCognitionEarthServer64.9.last";
            	
			DiaJobScheduler.DiaJS djs = new DiaJobScheduler.DiaJS();
			djs.Url = szServer;
            int ret = djs.SubmitJob(rootjob);
		}

		//-------------------------------------------------------
		//! CreateScene Creates a scene object
		//-------------------------------------------------------
		static Job CreateScene(string szName, int nLayers, int nExports)
		{
            Job job = new Job();

            job.mScene = new Scene();
            job.mScene.strName = new SString();
            job.mScene.strFilePath = new SString();
            job.mScene.iID = new SString();

			if(nLayers>0)
                job.mScene.vImgLayers = new ImgLayer[nLayers];
			if(nExports>0)
                job.mExportSpec = new ExportItem[nExports];

            job.eTask = EJobType.EAnalyse;
            job.mScene.iID.str = "1";
            job.mScene.iVer = 1;
            job.mScene.strName.str = szName;
            job.mScene.strFilePath.str = "";
            job.mScene.iSrc = 1;

            return job;
		}

		//-------------------------------------------------------
		//! CreateLayer Creates a layer object
		//-------------------------------------------------------
		static ImgLayer CreateLayer(string szName, string szPath)
		{
			ImgLayer layer1 = new ImgLayer();
			layer1.strAlias = new SString();
			layer1.strFilePath = new SString();

			layer1.strAlias.str = szName;
			layer1.strFilePath.str = GetFullPath(szPath);
			layer1.iIndx = 0;

			return layer1;
		}

		//-------------------------------------------------------
		//! CreateExportItem.  Creates an exported item object
		//-------------------------------------------------------
		static ExportItem CreateExportItem(string szName, string szPath, string szDriver, int Type)
		{
			ExportItem expitem1 = new ExportItem();
			expitem1.strName = new SString();
			expitem1.strPath = new SString();
			expitem1.strDriver = new SString();

			expitem1.strName.str = szName;
			expitem1.strPath.str = GetFullPath(szPath);
			expitem1.strDriver.str = szDriver;
			expitem1.iType = Type;
			return expitem1;
		}

		//-------------------------------------------------------
		//! GetFullPath
		//-------------------------------------------------------
		/*!
			For loclal servers the function translates a path from relational
			to an absolute path. For remote servers - does noithing, just returns
			the same path.
		  */
		static string GetFullPath(string szPath)
		{
			if(bLocal)
			{
				FileInfo fi = new FileInfo(szPath);
				return fi.FullName;
			}
			else
			{
				return szPath;
			}
		}

	}
}
