/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2016-2025, Regents of the University of California,
 *                          Colorado State University,
 *                          University Pierre & Marie Curie, Sorbonne University.
 *
 * This file is part of ndn-tools (Named Data Networking Essential Tools).
 * See AUTHORS.md for complete list of ndn-tools authors and contributors.
 *
 * ndn-tools is free software: you can redistribute it and/or modify it under the terms
 * of the GNU General Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later version.
 *
 * ndn-tools is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.  See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ndn-tools, e.g., in COPYING.md file.  If not, see <http://www.gnu.org/licenses/>.
 *
 * See AUTHORS.md for complete list of ndn-cxx authors and contributors.
 *
 * @author Wentao Shang
 * @author Steve DiBenedetto
 * @author Andrea Tosatto
 * @author Davide Pesavento
 * @author Weiwei Liu
 * @author Klaus Schneider
 * @author Chavoosh Ghasemi
 */

#include "consumer.hpp"
#include "discover-version.hpp"
#include "pipeline-interests-aimd.hpp"
#include "pipeline-interests-cubic.hpp"
#include "pipeline-interests-fixed.hpp"
#include "statistics-collector.hpp"
#include "core/version.hpp"

#include <ndn-cxx/security/validator-null.hpp>
#include <ndn-cxx/util/rtt-estimator.hpp>

#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/variables_map.hpp>

#include <fstream>
#include <iostream>

#include "inipp.h"

namespace ndn::get {

namespace po = boost::program_options;

// declaration of helper functions
static bool get_bool(std::string const& value, std::string const& errorMsg = "");

static int get_int(std::string const& value, std::string const& errorMsg = "");

static double get_double(std::string const& value, std::string const& errorMsg = "");

static long get_long(std::string const& value, std::string const& errorMsg = "");
// end of declaration

static int main(int argc, char* argv[])
{
  // Initialize options and variables
  Options options;
  std::string prefix, nameConv, pipelineType, configPath;
  std::string cwndPath, rttPath;
  auto rttEstOptions = std::make_shared<util::RttEstimator::Options>();
  const std::string programName(argv[0]);
  
  // Analyse command line options
  po::options_description basicDesc("Basic Options");
  basicDesc.add_options()
    ("help,h",      "print this help message and exit")
    ("config,c",    po::value<std::string>(&configPath),
                    "path to the configuration file")
    ("prefix,p",    po::value<std::string>(&prefix),
                    "NDN name of the requested content")
  ;
  
  po::variables_map vm;
  po::store(po::command_line_parser(argc, argv).options(basicDesc).run(), vm);
  po::notify(vm);

  if (vm.count("help") > 0) {
    std::cout << "Usage: " << programName << " [options]\n";
    std::cout << basicDesc;
    return 0;
  }

  if (vm.count("prefix") == 0) {
    std::cerr << "ERROR: --prefix is required\n";
    return 2;
  }

  if (vm.count("config") == 0) {
    std::cerr << "ERROR: --config is required\n";
    return 2;
  }

  configPath = vm.count("config") ? vm["config"].as<std::string>() : "";


  // Read from configuration (assert config is available)
  inipp::Ini<char> ini;
  std::ifstream configFile(configPath);

  // Determine if the configuration file exists and can be opened
  if (!configFile) {
    std::cerr << "ERROR: Could not open configuration file: " << configPath << "\n";
    return 1;
  }

  // Extract sections from the configuration file
  ini.parse(configFile);
  auto& general = ini.sections["general"];
  auto& pipeline = ini.sections["pipeline"];
  auto& aimd = ini.sections["aimd"];
  auto& cubic = ini.sections["cubic"];

  // Extract options from each section
  // general options
  options.mustBeFresh = get_bool(general["fresh"], "fresh");
  options.interestLifetime = time::milliseconds(get_long(general["lifetime"], "lifetime"));
  options.maxRetriesOnTimeoutOrNack = get_int(general["retries"], "retries");
  options.disableVersionDiscovery = get_bool(general["no-version-discovery"], "no-version-discovery");
  nameConv = general["naming-convention"];
  options.isQuiet = get_bool(general["quiet"], "quiet");
  options.isVerbose = get_bool(general["verbose"], "verbose");

  // pipeline options
  pipelineType = pipeline["pipeline-type"];
  options.maxPipelineSize = get_int(pipeline["pipeline-size"], "pipeline-size");
  options.ignoreCongMarks = get_bool(pipeline["ignore-marks"], "ignore-marks");
  options.disableCwa = get_bool(pipeline["disable-cwa"], "disable-cwa");
  options.initCwnd = get_double(pipeline["init-cwnd"], "init-cwnd");
  options.initSsthresh = get_double(pipeline["init-ssthresh"], "init-ssthresh");
  rttEstOptions->alpha = get_double(pipeline["rto-alpha"], "rto-alpha");
  rttEstOptions->beta = get_double(pipeline["rto-beta"], "rto-beta");
  rttEstOptions->k = get_int(pipeline["rto-k"], "rto-k");
  rttEstOptions->minRto = time::milliseconds(get_long(pipeline["min-rto"], "min-rto"));
  rttEstOptions->maxRto = time::milliseconds(get_long(pipeline["max-rto"], "max-rto"));
  cwndPath = pipeline["log-cwnd"];
  rttPath = pipeline["log-rtt"];
  options.rtoCheckInterval = time::milliseconds(get_long(pipeline["rto-check-interval"], "rto-check-interval"));
  rttEstOptions->initialRto = time::milliseconds(get_long(pipeline["initial-rto"], "initial-rto"));
  rttEstOptions->rtoBackoffMultiplier = get_double(pipeline["rto-backoff-multiplier"], "rto-backoff-multiplier");

  // aimd options
  options.aiStep = get_double(aimd["aimd-step"], "aimd-step");
  options.mdCoef = get_double(aimd["aimd-beta"], "aimd-beta");
  options.resetCwndToInit = get_bool(aimd["reset-cwnd-to-init"], "reset-cwnd-to-init");

  // cubic options
  options.cubicBeta = get_double(cubic["cubic-beta"], "cubic-beta");
  options.enableFastConv = get_bool(cubic["fast-conv"], "fast-conv");

  // checking configured options
  if (nameConv == "marker" || nameConv == "m" || nameConv == "1") {
    name::setConventionEncoding(name::Convention::MARKER);
  }
  else if (nameConv == "typed" || nameConv == "t" || nameConv == "2") {
    name::setConventionEncoding(name::Convention::TYPED);
  }
  else if (!nameConv.empty()) {
    std::cerr << "ERROR: '" << nameConv << "' is not a valid naming convention\n";
    return 2;
  }

  if (options.interestLifetime < 0_ms) {
    std::cerr << "ERROR: --lifetime cannot be negative\n";
    return 2;
  }

  if (options.maxRetriesOnTimeoutOrNack < -1 || options.maxRetriesOnTimeoutOrNack > 1024) {
    std::cerr << "ERROR: --retries must be between -1 and 1024\n";
    return 2;
  }

  if (options.isQuiet && options.isVerbose) {
    std::cerr << "ERROR: cannot be quiet and verbose at the same time\n";
    return 2;
  }

  if (options.maxPipelineSize < 1 || options.maxPipelineSize > 1024) {
    std::cerr << "ERROR: --pipeline-size must be between 1 and 1024\n";
    return 2;
  }

  if (rttEstOptions->k < 0) {
    std::cerr << "ERROR: --rto-k cannot be negative\n";
    return 2;
  }

  if (rttEstOptions->minRto < 0_ms) {
    std::cerr << "ERROR: --min-rto cannot be negative\n";
    return 2;
  }

  if (rttEstOptions->maxRto < rttEstOptions->minRto) {
    std::cerr << "ERROR: --max-rto cannot be smaller than --min-rto\n";
    return 2;
  }

  // main logic
  try {
    Face face;
    auto discover = std::make_unique<DiscoverVersion>(face, Name(prefix), options);
    std::unique_ptr<PipelineInterests> pipeline;
    std::unique_ptr<StatisticsCollector> statsCollector;
    std::unique_ptr<RttEstimatorWithStats> rttEstimator;
    std::ofstream statsFileCwnd;
    std::ofstream statsFileRtt;

    if (pipelineType == "fixed") {
      pipeline = std::make_unique<PipelineInterestsFixed>(face, options);
    }
    else if (pipelineType == "aimd" || pipelineType == "cubic") {
      if (options.isVerbose) {
        using namespace ndn::time;
        std::cerr << "RTT estimator parameters:\n"
                  << "\tAlpha = " << rttEstOptions->alpha << "\n"
                  << "\tBeta = " << rttEstOptions->beta << "\n"
                  << "\tK = " << rttEstOptions->k << "\n"
                  << "\tInitial RTO = " << duration_cast<milliseconds>(rttEstOptions->initialRto) << "\n"
                  << "\tMin RTO = " << duration_cast<milliseconds>(rttEstOptions->minRto) << "\n"
                  << "\tMax RTO = " << duration_cast<milliseconds>(rttEstOptions->maxRto) << "\n"
                  << "\tBackoff multiplier = " << rttEstOptions->rtoBackoffMultiplier << "\n";
      }
      rttEstimator = std::make_unique<RttEstimatorWithStats>(std::move(rttEstOptions));

      std::unique_ptr<PipelineInterestsAdaptive> adaptivePipeline;
      if (pipelineType == "aimd") {
        adaptivePipeline = std::make_unique<PipelineInterestsAimd>(face, *rttEstimator, options);
      }
      else {
        adaptivePipeline = std::make_unique<PipelineInterestsCubic>(face, *rttEstimator, options);
      }

      if (!cwndPath.empty() || !rttPath.empty()) {
        if (!cwndPath.empty()) {
          statsFileCwnd.open(cwndPath);
          if (statsFileCwnd.fail()) {
            std::cerr << "ERROR: failed to open '" << cwndPath << "'\n";
            return 4;
          }
        }
        if (!rttPath.empty()) {
          statsFileRtt.open(rttPath);
          if (statsFileRtt.fail()) {
            std::cerr << "ERROR: failed to open '" << rttPath << "'\n";
            return 4;
          }
        }
        statsCollector = std::make_unique<StatisticsCollector>(*adaptivePipeline, statsFileCwnd, statsFileRtt);
      }

      pipeline = std::move(adaptivePipeline);
    }
    else {
      std::cerr << "ERROR: '" << pipelineType << "' is not a valid pipeline type\n";
      return 2;
    }

    Consumer consumer(security::getAcceptAllValidator());
    BOOST_ASSERT(discover != nullptr);
    BOOST_ASSERT(pipeline != nullptr);
    consumer.run(std::move(discover), std::move(pipeline));
    face.processEvents();
  }
  catch (const Consumer::ApplicationNackError& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 3;
  }
  catch (const Consumer::DataValidationError& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 5;
  }
  catch (const std::exception& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 1;
  }

  return 0;
}

// helper functions
static bool get_bool(std::string const& value, std::string const& errorMsg)
{
  if (value == "true") {
    return true;
  } else if (value == "false") {
    return false;
  } else {
    std::cerr << "ERROR: Invalid boolean value from consumer option " << errorMsg << ": " << value << ", only allows true/false\n";
    exit(1);
  }
}

static long get_long(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<long>::max();
  }
  try {
    return std::stol(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid long value from consumer option " << errorMsg << ": " << value << "\n";
    exit(1); 
  }
}

static int get_int(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<int>::max();
  }
  try {
    return std::stoi(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid integer value from consumer option " << errorMsg << ": " << value << "\n";
    exit(1); 
  }
}

static double get_double(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<double>::max();
  }
  try {
    return std::stod(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid double value from consumer option " << errorMsg << ": " << value << "\n";
  }
}

} // namespace ndn::get

int
main(int argc, char* argv[])
{
  return ndn::get::main(argc, argv);
}
