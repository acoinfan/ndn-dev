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
            #ifdef MODE_OLD
                std::string socketPath = "unix:///run/nfd/" + prefix + ".sock";
            #else
                std::string socketPath = "unix:///run/nfd/client" + std::to_string(producerId) + ".sock";
            #endif
            
            auto transport = ndn::UnixTransport::create(socketPath);
            Face face(transport);
            KeyChain keyChain;
            Producer producer(prefix, face, keyChain, fileDir, logFile, options);

            sendConsumerSignal();
            if (options.isVerbose)
            {
                logFile << prefix << " is ready!" << std::endl;
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