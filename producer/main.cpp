#include "producer.hpp"

#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/variables_map.hpp>
#include <boost/property_tree/ptree.hpp>
#include <boost/property_tree/ini_parser.hpp>
#include <iostream>

#include "inipp.h"

namespace ndn::chunks
{
    namespace po = boost::program_options;

    // declaration of helper functions
    static bool get_bool(std::string const &value, std::string const &errorMsg = "");

    static int get_int(std::string const &value, std::string const &errorMsg = "");

    static double get_double(std::string const &value, std::string const &errorMsg = "");

    static long get_long(std::string const &value, std::string const &errorMsg = "");
    // end of declaration

    static int
    main(int argc, char *argv[])
    {
        // Initialize options and variables
        const std::string programName(argv[0]);

        Producer::Options options;
        std::string prefix, nameConv, signingInfo, configPath, fileDir; // 默认配置文件路径

        // Analyse command line options
        po::options_description basicDesc("Options");
        basicDesc.add_options()
        ("help,h", "print this help message and exit")
        ("prefix,p", po::value<std::string>(&prefix)->required(), "NDN name for the served content")
        ("config,c", po::value<std::string>(&configPath)->required(), "ConfigPath for the producer")
        ("directory,d", po::value<std::string>(&fileDir)->required(), "Directory of files to send (absolute path)");
        
        po::variables_map vm;
        po::store(po::command_line_parser(argc, argv).options(basicDesc).run(), vm);
        po::notify(vm);

        if (vm.count("help") > 0)
        {
            std::cout << "Usage: " << programName << " [options]\n";
            std::cout << basicDesc;
            return 0;
        }

        if (vm.count("prefix") == 0)
        {
            std::cerr << "ERROR: --prefix is required\n";
            return 2;
        }

        if (vm.count("config") == 0)
        {
            std::cerr << "ERROR: --config is required\n";
            return 2;
        }

        configPath = vm.count("config") ? vm["config"].as<std::string>() : "";

        // Read from configuration (assert config is available)
        inipp::Ini<char> ini;
        std::ifstream configFile(configPath);

        // Determine if the configuration file exists and can be opened
        if (!configFile)
        {
            std::cerr << "ERROR: Could not open configuration file: " << configPath << "\n";
            return 1;
        }

        // Extract sections from the configuration file
        ini.parse(configFile);
        auto &general = ini.sections["general"];

        // Extract options from each section
        // general options
        options.freshnessPeriod = time::milliseconds(get_long(general["freshness"], "freshness"));
        options.maxSegmentSize = get_int(general["segment-size"], "segment-size");
        nameConv = general["naming-convention"];
        signingInfo = general["signing-info"];
        options.isQuiet = get_bool(general["quiet"], "quiet");
        options.isVerbose = get_bool(general["verbose"], "verbose");

        // checking configured options
        if (nameConv == "marker" || nameConv == "m" || nameConv == "1")
        {
            name::setConventionEncoding(name::Convention::MARKER);
        }
        else if (nameConv == "typed" || nameConv == "t" || nameConv == "2")
        {
            name::setConventionEncoding(name::Convention::TYPED);
        }
        else if (!nameConv.empty())
        {
            std::cerr << "ERROR: '" << nameConv << "' is not a valid naming convention\n";
            return 2;
        }

        if (options.freshnessPeriod < 0_ms)
        {
            std::cerr << "ERROR: --freshness cannot be negative\n";
            return 2;
        }

        if (options.maxSegmentSize < 1 || options.maxSegmentSize > MAX_NDN_PACKET_SIZE)
        {
            std::cerr << "ERROR: --size must be between 1 and " << MAX_NDN_PACKET_SIZE << "\n";
            return 2;
        }

        try
        {
            options.signingInfo = security::SigningInfo(signingInfo);
        }
        catch (const std::invalid_argument &e)
        {
            std::cerr << "ERROR: " << e.what() << "\n";
            return 2;
        }

        if (options.isQuiet && options.isVerbose)
        {
            std::cerr << "ERROR: cannot be quiet and verbose at the same time\n";
            return 2;
        }

        try
        {
            Face face;
            KeyChain keyChain;
            Producer producer(prefix, face, keyChain, options, fileDir);
            producer.run();
        }
        catch (const std::exception &e)
        {
            std::cerr << "ERROR: " << e.what() << "\n";
            return 1;
        }

        return 0;
    }

    // helper functions
    static bool get_bool(std::string const &value, std::string const &errorMsg)
    {
        if (value == "true")
        {
            return true;
        }
        else if (value == "false")
        {
            return false;
        }
        else
        {
            std::cerr << "ERROR: Invalid boolean value from producer option " << errorMsg << ": " << value << ", only allows true/false\n";
            exit(1);
        }
    }

    static long get_long(std::string const &value, std::string const &errorMsg)
    {
        if (value == "max")
        {
            return std::numeric_limits<long>::max();
        }
        try
        {
            return std::stol(value);
        }
        catch (const std::invalid_argument &)
        {
            std::cerr << "ERROR: Invalid long value from producer option " << errorMsg << ": " << value << "\n";
            exit(1);
        }
    }

    static int get_int(std::string const &value, std::string const &errorMsg)
    {
        if (value == "max")
        {
            return std::numeric_limits<int>::max();
        }
        try
        {
            return std::stoi(value);
        }
        catch (const std::invalid_argument &)
        {
            std::cerr << "ERROR: Invalid integer value from producer option " << errorMsg << ": " << value << "\n";
            exit(1);
        }
    }

    static double get_double(std::string const &value, std::string const &errorMsg)
    {
        if (value == "max")
        {
            return std::numeric_limits<double>::max();
        }
        try
        {
            return std::stod(value);
        }
        catch (const std::invalid_argument &)
        {
            std::cerr << "ERROR: Invalid double value from producer option " << errorMsg << ": " << value << "\n";
        }
    }

}

int main(int argc, char *argv[])
{
    std::remove("logs/producer.log");
    return ndn::chunks::main(argc, argv);
}