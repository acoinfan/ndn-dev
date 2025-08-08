#ifndef CLIENT_ASYNC_CONSUMER_HPP
#define CLIENT_ASYNC_CONSUMER_HPP

#include "consumer.hpp"
#include "discover-version.hpp"
#include "pipeline-interests-aimd.hpp"
#include "pipeline-interests-cubic.hpp"
#include "pipeline-interests-fixed.hpp"
#include "statistics-collector.hpp"
#include "core/version.hpp"

#include <ndn-cxx/security/validator-null.hpp>
#include <ndn-cxx/util/rtt-estimator.hpp>
#include <thread>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/basic_file_sink.h>
#include <ndn-cxx/transport/unix-transport.hpp>
#include <atomic>
#include "consumer.hpp"

namespace ndn::get
{

    class AsyncConsumer
    {
    private:
        int consumerId, producerId;
        std::thread consumerThread;
        std::atomic<int> exitCode{-1};
        std::string prefix; // consumer0-1
        bool cwndLoggingEnabled;
        bool rttLoggingEnabled;
        bool isSaveFile;

        const std::string pipelineType;
        const std::string fileName;
        const std::string fileDir;
        const Options options;
        const util::RttEstimator::Options rttEstOptions;

    public:
        AsyncConsumer(int consumerId, int producerId, bool isSaveFile, bool cwndLoggingEnabled, bool rttLoggingEnabled, const std::string &fileName, const std::string &fileDir, const std::string &pipelineType, const Options &options, const util::RttEstimator::Options &rttEstOptions)
            : consumerId(consumerId), producerId(producerId), isSaveFile(isSaveFile), cwndLoggingEnabled(cwndLoggingEnabled), rttLoggingEnabled(rttLoggingEnabled), fileName(fileName), fileDir(fileDir), pipelineType(pipelineType), options(options), rttEstOptions(rttEstOptions)
        {
            prefix = "consumer" + std::to_string(consumerId) + "-" + std::to_string(producerId);
        }

        void start()
        {
            consumerThread = std::thread([this]()
                                         { this->exitCode.store(this->runConsumerMain()); });
        }

        void join()
        {
            if (consumerThread.joinable())
            {
                consumerThread.join();
            }
        }

        int getExitCode() const
        {
            return exitCode.load();
        }

        bool isFinished() const
        {
            return exitCode.load() != -1;
        }

    private:
        int runConsumerMain()
        {
            std::string logFilePath = "/tmp/ndn/" + prefix + ".log";
            std::ofstream logFile(logFilePath);
            try
            {
                std::string socketPath = "unix:///run/nfd/consumer" + std::to_string(consumerId) + ".sock";
                auto transport = ndn::UnixTransport::create(socketPath);
                Face face(transport);

                // create the interest prefix (eg. /producer1/file.txt)
                std::string interestPrefix = "/producer" + std::to_string(producerId) + "/" + fileName;
                auto discover = std::make_unique<DiscoverVersion>(face, Name(interestPrefix), options);
                std::unique_ptr<PipelineInterests> pipeline;
                std::unique_ptr<StatisticsCollector> statsCollector;
                std::unique_ptr<RttEstimatorWithStats> rttEstimator;
                std::ofstream statsFileCwnd, statsFileRtt;

                auto rttEstOptionsCopy = std::make_shared<util::RttEstimator::Options>(rttEstOptions);

                if (pipelineType == "fixed")
                {
                    pipeline = std::make_unique<PipelineInterestsFixed>(face, options);
                }
                else if (pipelineType == "aimd" || pipelineType == "cubic")
                {
                    if (options.isVerbose)
                    {
                        using namespace ndn::time;
                        std::cerr << "RTT estimator parameters:\n"
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
                    if (pipelineType == "aimd")
                    {
                        adaptivePipeline = std::make_unique<PipelineInterestsAimd>(face, *rttEstimator, options);
                    }
                    else
                    {
                        adaptivePipeline = std::make_unique<PipelineInterestsCubic>(face, *rttEstimator, options);
                    }

                    if (cwndLoggingEnabled || rttLoggingEnabled)
                    {
                        if (cwndLoggingEnabled)
                        {
                            std::string cwndPath = "/tmp/ndn/" + prefix + "-cwnd.log";
                            statsFileCwnd.open(cwndPath);
                            if (statsFileCwnd.fail())
                            {
                                std::cerr << "ERROR: failed to open '" << cwndPath << "'\n";
                                return 4;
                            }
                        }

                        if (rttLoggingEnabled)
                        {
                            std::string rttPath = "/tmp/ndn/" + prefix + "-rtt.log";
                            statsFileRtt.open(rttPath);
                            if (statsFileRtt.fail())
                            {
                                std::cerr << "ERROR: failed to open '" << rttPath << "'\n";
                                return 4;
                            }
                        }
                        statsCollector = std::make_unique<StatisticsCollector>(*adaptivePipeline, statsFileCwnd, statsFileRtt);
                    }

                    pipeline = std::move(adaptivePipeline);
                }
                else
                {
                    std::cerr << "ERROR: '" << pipelineType << "' is not a valid pipeline type\n";
                    return 2;
                }

                std::ofstream outputStream;
                if (isSaveFile)
                {
                    // fileDir must be absolute path
                    // will save file to /<fileDir>/<producerId>-<fileName>
                    std::string outputPath = fileDir + "/" + std::to_string(producerId) + "-" + fileName;
                    outputStream.open(outputPath);
                    if (outputStream.fail())
                    {
                        std::cerr << "ERROR: failed to open '" << outputPath << "'\n";
                        return 4;
                    }
                }
                else
                {
                    // if not saving file, we can use /dev/null to discard output
                    // this avoids creating an empty file
                    outputStream.open("/dev/null");
                    if (outputStream.fail())
                    {
                        std::cerr << "ERROR: failed to open '/dev/null'\n";
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

    }; // class AsyncConsumer
} // namespace ndn::get
#endif // CLIENT_ASYNC_CONSUMER_HPP