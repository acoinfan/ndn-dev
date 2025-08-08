#include "async-consumer.hpp"

namespace ndn::get
{
  AsyncConsumer::AsyncConsumer(int consumerId, int producerId, const AsyncConsumerOptions &asyncOptions, const Options &options, const util::RttEstimator::Options &rttEstOptions)
      : consumerId(consumerId), producerId(producerId), asyncOptions(asyncOptions), options(options), rttEstOptions(rttEstOptions)
  {
    prefix = "con" + std::to_string(consumerId) + "-" + std::to_string(producerId);
  }

  void AsyncConsumer::start()
  {
    consumerThread = std::thread([this]()
                                 { this->exitCode.store(this->runConsumerMain()); });
  }

  void AsyncConsumer::join()
  {
    if (consumerThread.joinable())
    {
      consumerThread.join();
    }
  }

  int AsyncConsumer::getExitCode() const
  {
    return exitCode.load();
  }

  bool AsyncConsumer::isFinished() const
  {
    return exitCode.load() != -1;
  }

  int AsyncConsumer::runConsumerMain()
  {
    std::string logFilePath = "/tmp/ndn/" + prefix + ".log";
    std::ofstream logFile(logFilePath);
    try
    {
      // Build the socket for the consumer
      waitForProducer(logFile);

      std::string socketPath = "unix:///run/nfd/con" + std::to_string(consumerId) + "-" + std::to_string(producerId) + ".sock";
      auto transport = ndn::UnixTransport::create(socketPath);
      Face face(transport);

      // Create the interest prefix (eg. /producer1/file.txt)
      std::string interestPrefix = "/pro" + std::to_string(producerId) + "/" + asyncOptions.fileName;
      auto discover = std::make_unique<DiscoverVersion>(face, Name(interestPrefix), options);
      std::unique_ptr<PipelineInterests> pipeline;
      std::unique_ptr<StatisticsCollector> statsCollector;
      std::unique_ptr<RttEstimatorWithStats> rttEstimator;
      std::ofstream statsFileCwnd, statsFileRtt;

      auto rttEstOptionsCopy = std::make_shared<util::RttEstimator::Options>(rttEstOptions);

      // Handle the pipeline type
      if (asyncOptions.pipelineType == "fixed")
      {
        pipeline = std::make_unique<PipelineInterestsFixed>(face, options, logFile);
      }
      else if (asyncOptions.pipelineType == "aimd" || asyncOptions.pipelineType == "cubic")
      {
        if (options.isVerbose)
        {
          using namespace ndn::time;
          logFile << "RTT estimator parameters:\n"
                    << "\tAlpha = " << rttEstOptions.alpha << "\n"
                    << "\tBeta = " << rttEstOptions.beta << "\n"
                    << "\tK = " << rttEstOptions.k << "\n"
                    << "\tInitial RTO = " << duration_cast<milliseconds>(rttEstOptions.initialRto) << "\n"
                    << "\tMin RTO = " << duration_cast<milliseconds>(rttEstOptions.minRto) << "\n"
                    << "\tMax RTO = " << duration_cast<milliseconds>(rttEstOptions.maxRto) << "\n"
                    << "\tBackoff multiplier = " << rttEstOptions.rtoBackoffMultiplier << "\n";
        }
        rttEstimator = std::make_unique<RttEstimatorWithStats>(std::move(rttEstOptionsCopy));

        std::unique_ptr<PipelineInterestsAdaptive> adaptivePipeline;
        if (asyncOptions.pipelineType == "aimd")
        {
          adaptivePipeline = std::make_unique<PipelineInterestsAimd>(face, *rttEstimator, options, logFile); 
        }
        else
        {
          adaptivePipeline = std::make_unique<PipelineInterestsCubic>(face, *rttEstimator, options, logFile);  
        }

        // Determine whether to log cwnd and RTT
        if (asyncOptions.cwndLoggingEnabled || asyncOptions.rttLoggingEnabled)
        {
          if (asyncOptions.cwndLoggingEnabled)
          {
            std::string cwndPath = "/tmp/ndn/" + prefix + "-cwnd.log";
            statsFileCwnd.open(cwndPath);
            if (statsFileCwnd.fail())
            {
              logFile << prefix << " ERROR: failed to open '" << cwndPath << "'\n";
              return 4;
            }
          }

          if (asyncOptions.rttLoggingEnabled)
          {
            std::string rttPath = "/tmp/ndn/" + prefix + "-rtt.log";
            statsFileRtt.open(rttPath);
            if (statsFileRtt.fail())
            {
              logFile << prefix << " ERROR: failed to open '" << rttPath << "'\n";
              return 4;
            }
          }
          statsCollector = std::make_unique<StatisticsCollector>(*adaptivePipeline, statsFileCwnd, statsFileRtt);
        }

        pipeline = std::move(adaptivePipeline);
      }
      else
      {
        logFile << prefix << " ERROR: '" << asyncOptions.pipelineType << "' is not a valid pipeline type\n";
        return 2;
      }

      // Determine whether to save the file
      std::ofstream outputStream;
      if (asyncOptions.isSaveFile)
      {
        // fileDir must be absolute path
        // will save file to /<fileDir>/<producerId>-<fileName>
        std::string outputPath = asyncOptions.fileDir + "/" + std::to_string(producerId) + "-" + asyncOptions.fileName;
        outputStream.open(outputPath);
        if (outputStream.fail())
        {
          logFile << prefix << " ERROR: failed to open '" << outputPath << "'\n";
          return 4;
        }
      }
      else
      {
        // If not saving file, we can use /dev/null to discard output
        outputStream.open("/dev/null");
        if (outputStream.fail())
        {
          logFile << prefix << " ERROR: failed to open '/dev/null'\n";
          return 4;
        }
      }

      Consumer consumer(security::getAcceptAllValidator(), outputStream);
      BOOST_ASSERT(discover != nullptr);
      BOOST_ASSERT(pipeline != nullptr);
      consumer.run(std::move(discover), std::move(pipeline));
      face.processEvents();

      return 0;
    }
    // handling errors
    catch (const Consumer::ApplicationNackError &e)
    {
      logFile << prefix << " ERROR: " << e.what() << "\n";
      return 3;
    }
    catch (const Consumer::DataValidationError &e)
    {
      logFile << prefix << " ERROR: " << e.what() << "\n";
      return 5;
    }
    catch (const std::exception &e)
    {
      logFile << prefix << " ERROR: " << e.what() << "\n";
      return 1;
    }
  }


  void AsyncConsumer::waitForProducer(std::ofstream &logFile) {
    if (options.isVerbose) {
        logFile << prefix << " waiting for producer ready signal: " << asyncOptions.signalFile << std::endl;
    }
    
    auto startTime = std::chrono::steady_clock::now();
    
    while (true) {
        // check if the signal file exists
        if (std::ifstream(asyncOptions.signalFile).good()) {
            if (options.isVerbose) {
                logFile << prefix << " received producer ready signal!" << std::endl;
            }
            return;  
        }
        
        // check if the wait timeout has been exceeded
        auto elapsed = std::chrono::steady_clock::now() - startTime;
        if (elapsed > waitTimeout) {
            throw std::runtime_error("Timeout waiting for producer ready signal (30 seconds)");
        }
        // every 100 milliseconds, check again
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}
} // namespace ndn::get
