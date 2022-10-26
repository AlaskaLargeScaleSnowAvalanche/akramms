#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <iostream>
#include <fstream>

/** This script meant to be compiled with MinGW and run on Windows. */

int main(int argc, char **argv)
{
    std::vector<std::string> args;
    for (int i=0; i<argc; ++i) args.push_back(std::string(argv[i]));

    // Get the directory this exe was launched from
    auto &script(args[0]);
    size_t slash = script.rfind('\\', std::string::npos);
    std::string const exe_dir(&script[0], &script[slash]);
//    printf("exe_dir %s\n", exe_dir.c_str());

    if (argc == 4) {
        // ramms_aval_LHM.exe juneau1_For_5m_30L_11392.av2 C write_xy
        // Pass through
        std::string cmd = exe_dir + "\\ramms_aval_LHM_orig.exe";
        for (int i=1; ;) {
            cmd += " ";
            cmd += args[i];
            ++i;
            if (i >= args.size()) break;
        }
        printf("%s\n", cmd.c_str());
        return system(cmd.c_str());
    } else if (argc == 3) {
        // ramms_aval_LHM.exe juneau1_For_5m_30L_11392.av2 juneau1_For_5m_30L_11392.out
        // Capture this call, do not run
        printf("Not running RAMMS: %s", argv[0]);
        for (int i=1; i<argc; ++i) {
            printf(" %s", argv[i]);
        }
        printf("\n");

#if 0
        // Create an "out2.bat" file
        std::string const &out_file(args[2]);
        std::string const out2_file = out_file + "2";
        
        std::ofstream out;
        out.open(out2_file + ".bat");
        out << exe_dir << "\\ramms_aval_LHM_orig.exe";
        for (size_t i=1; i<args.size()-1; ++i) out << " " << args[i];
        out << " " << args[args.size()-1] << "2" << std::endl;

        out << exe_dir << "\\gzip.exe -f " << out_file << "2" << std::endl;
        out << "echo Simulation finished successfully > " << out_file << "2.end";
        out.close();
#endif
        return 0;
        
    }
}

