#include "producer.hpp"

#include <ndn-cxx/metadata-object.hpp>
#include <ndn-cxx/util/segmenter.hpp>
#include <iostream>

#include <boost/lexical_cast.hpp>
namespace ndn::chunks
{
    // to do: Dataset ID - rubbish
    Producer::Producer(const Name &prefix, Face &face, KeyChain &keyChain,
                       const Options &opts, uint64_t datasetId)
        : m_face(face), m_keyChain(keyChain), m_options(opts), m_datasetId(datasetId)
    {
        spdlog::debug("Producer::Producer()");

        m_prefix = prefix;
        if (!m_options.isQuiet)
        {
            std::cerr << "Loading input ...\n";
            spdlog::info("Loading input ...");
        }
        // Segmenter segmenter(m_keyChain, m_options.signingInfo);
        // // All the data packets are segmented and stored in m_store
        // m_store[chunkNumber] = segmenter.segment(is, m_chunkedPrefix, m_options.maxSegmentSize, m_options.freshnessPeriod);
        // register m_prefix without Interest handler
        spdlog::debug("Registering prefix {}", m_prefix.toUri());
        // 注册前缀到ndn网络
        m_face.registerPrefix(m_prefix, nullptr, [this](const Name &prefix, const auto &reason)
                              {            
            spdlog::error("ERROR: Failed to register prefix '{}'({})", prefix.toUri(), boost::lexical_cast<std::string>(reason));
            m_face.shutdown(); });
        // 设置Interest过滤器，处理分段请求
        face.setInterestFilter(m_prefix, [this](const auto &, const auto &interest)
                               { processSegmentInterest(interest); });
    }

    void
    Producer::run()
    {
        spdlog::debug("Producer::run()");
        m_face.processEvents();
    }

    void
    Producer::processSegmentInterest(const Interest &interest)
    {
        spdlog::debug("Producer::processSegmentInterest()");
        if (m_options.isVerbose)
        {
            std::cerr << "Interest: " << interest << "\n";
            spdlog::info("Interest: {}", interest.getName().toUri());
        }
        // 处理无效请求
        if (static_cast<uint64_t>(std::stoi(interest.getName().get(1).toUri())) != m_datasetId)
        {
            spdlog::info("Interest name does not match the dataset ID of {}", m_prefix.toUri());
            return;
        }
        // 获取前缀
        const Name &prefix = interest.getName().getPrefix(-1);
        std::string prefixstr = prefix.toUri();

        // 未分段，则分段
        if (m_store[prefixstr].empty())
        {
            // spdlog::debug("temporarily no data");
            // return;
            segmentationFile(interest);
        }
        BOOST_ASSERT(!m_store[prefixstr].empty());

        std::shared_ptr<Data> data;

        // 指定segment: 请求对应segment
        if (interest.getName().get(-1).isSegment())
        {
            const auto segmentNo = static_cast<size_t>(interest.getName()[-1].toSegment());
            // specific segment retrieval
            if (segmentNo < m_store[prefixstr].size())
            {
                data = m_store[prefixstr][segmentNo];
                m_nSentSegments[prefixstr]++;
            }
        }
        // 不指定segment: 返回第一个segment
        else if (interest.matchesData(*m_store[prefixstr][0]))
        {

            // unspecified version or segment number, return first segment
            data = m_store[prefixstr][0];
            m_nSentSegments[prefixstr] = 1;
        }

        if (data != nullptr)
        {
            if (m_options.isVerbose)
            {
                std::cerr << "Data: " << *data << "\n";
                spdlog::info("Data: {}", (*data).getName().toUri());
                spdlog::debug("Data TLV type: {}", data->wireEncode().type());
            }
            // 将Data包发送到网络
            m_face.put(*data);

            // check all the segments are sent
            const Name &dataName = data->getName();
            if (dataName[-1].isSegment())
            {
                uint64_t sentSegments = m_nSentSegments[prefixstr];
                auto it = m_store.find(prefixstr);
                if (it != m_store.end())
                {
                    size_t totalSegments = it->second.size();
                    if (sentSegments == totalSegments)
                    {
                        m_store.erase(prefixstr);
                        spdlog::debug("Cleared prefixstr {} after sending {} segments ", prefixstr, sentSegments);
                    }
                }
            }
        }
        else
        {
            if (m_options.isVerbose)
            {
                std::cerr << "Interest cannot be satisfied, sending Nack\n";
                spdlog::info("Interest cannot be satisfied, sending Nack");
            }
            m_face.put(lp::Nack(interest));
        }
    }

    void
    Producer::segmentationFile(const Interest &interest)

    {
        const Name &prefix = interest.getName().getPrefix(-1);
        std::string prefixstr = prefix.toUri();
        std::string filePathStr;
        if (prefix.size() >= 3)
        {
            // 提取文件名（从第2个组件开始，跳过前缀和datasetId）
            Name filePath = prefix.getSubName(2);
            filePathStr = filePath.toUri();
            filePathStr = "/home/a_coin_fan/code/ndn-dev/experiments/" + std::to_string(m_datasetId) + filePathStr;
            spdlog::debug("Extracted file path: {}", filePathStr);
        }
        else
        {
            spdlog::error("Interest name does not have enough components for file path extraction");
            return;
        }

        std::unique_ptr<std::istream> is = std::make_unique<std::ifstream>(filePathStr, std::ios::binary);

        if (!is || !(*is))
        {
            spdlog::error("Failed to open file: {}", filePathStr);
            return;
        }
        if (!m_options.isQuiet)
        {
            std::cerr << "Loading input ...\n";
            spdlog::info("Loading input ...");
        }
        Segmenter segmenter(m_keyChain, m_options.signingInfo);
        // All the data packets are segmented and stored in m_store
        m_store[prefixstr] = segmenter.segment(*is, prefix, m_options.maxSegmentSize, m_options.freshnessPeriod);
        if (!m_options.isQuiet)
        {
            std::cerr << "Published " << m_store[prefixstr].size() << " Data packet" << (m_store[prefixstr].size() > 1 ? "s" : "")
                      << "\n";
            spdlog::info("Published {} Data packet(s)", m_store[prefixstr].size());
        }
    }

} // namespace ndn::chunks