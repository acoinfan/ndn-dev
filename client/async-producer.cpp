#include "async-producer.hpp"

namespace ndn::serve
{

    AsyncProducer::AsyncProducer(int producerId, const std::string &fileDir, const ndn::serve::Producer::Options &options)
        : producerId(producerId), fileDir(fileDir), options(options)
    {
        prefix = "pro" + std::to_string(producerId);
    }

    void AsyncProducer::start()
    {
        producerThread = std::thread([this]()
                                     { this->exitCode.store(this->runProducerMain()); });
    }

    void AsyncProducer::join()
    {
        if (producerThread.joinable())
        {
            producerThread.join();
        }
    }

    int AsyncProducer::getExitCode() const
    {
        return exitCode.load();
    }

    bool AsyncProducer::isFinished() const
    {
        return exitCode.load() != -1;
    }

    int AsyncProducer::runProducerMain()
    {
        std::string logFilePath = "/tmp/ndn/" + prefix + ".log";
        std::ofstream logFile(logFilePath);
        try
        {
            std::string socketPath = "unix:///run/nfd/" + prefix + ".sock";
            auto transport = ndn::UnixTransport::create(socketPath);
            Face face(transport);
            KeyChain keyChain;

            // for temporary test
            std::string filePath = "/home/a_coin_fan/code/ndn-dev/experiments/testfile_6442450.txt";
            std::string fileName = "testfile_6442450.txt";
            std::ifstream inputFile(filePath);
            if (!inputFile)
            {
                logFile << prefix << " ERROR: Failed to open input file: " << filePath << std::endl;
                return 1;
            }

            Producer producer(prefix, face, keyChain, fileName, inputFile, logFile, options);

            sendConsumerSignal();
            if (options.isVerbose)
            {
                logFile << prefix << " is ready! \n";
            }

            producer.run();
            logFile << std::flush;
            return 0;
        }
        catch (const std::exception &e)
        {
            logFile << prefix << " ERROR: " << e.what() << std::endl;
            return 1;
        }
        return 0;
    }

    void AsyncProducer::sendConsumerSignal()
    {
        std::filesystem::create_directories("/tmp/ndn");
        std::string signalFilePath = "/tmp/ndn/" + prefix + ".ok";
        std::ofstream signalFile(signalFilePath);
        if (signalFile.is_open())
        {
            signalFile << prefix << " is ready!" << std::endl;
            signalFile.close();
        }
        else
        {
            throw std::runtime_error("Failed to create signal file: " + signalFilePath);
        }
    }
} // namespace ndn::chunks