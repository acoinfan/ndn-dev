#include "producer.hpp"

#include <ndn-cxx/metadata-object.hpp>
#include <ndn-cxx/util/segmenter.hpp>
#include <iostream>
#include <boost/lexical_cast.hpp>
namespace ndn::chunks
{
    Producer::Producer(const Name &prefix, Face &face, KeyChain &keyChain,
                       const Options &opts, std::string fileDir)
        : m_face(face), m_keyChain(keyChain), m_options(opts), m_prefix(prefix), m_fileDir(fileDir)
    {
        if (!m_options.isQuiet)
        {
            std::cerr << "Loading input ...\n";
        }

        // 注册前缀到ndn网络
        m_face.registerPrefix(m_prefix, nullptr, [this](const Name &prefix, const auto &reason)
                              {
            std::cerr << "ERROR: Failed to register prefix '" << prefix.toUri() << "'(" << boost::lexical_cast<std::string>(reason) << ")" << std::endl;
            m_face.shutdown(); });
        // 设置Interest过滤器，处理分段请求
        face.setInterestFilter(m_prefix, [this](const auto &, const auto &interest)
                               { processSegmentInterest(interest); });

        if (!m_options.isQuiet)
        {                     
        std::cerr << "Producer is ready for prefix: " << m_prefix.toUri() << "\n";
        }
    }

    void
    Producer::run()
    {
        m_face.processEvents();
    }

    void
    Producer::processSegmentInterest(const Interest &interest)
    {
        if (m_options.isVerbose)
        {
            std::cerr << "Interest: " << interest << "\n";
        }

        // 获取前缀
        const Name &prefix = interest.getName().getPrefix(-1);
        std::string prefixstr = prefix.toUri();

        // 未分段，则分段
        if (m_store[prefixstr].empty())
        {
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
                std::cerr << "Data: " << *data << "\n";;
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
                    }
                }
            }
        }
        else
        {
            if (m_options.isVerbose)
            {
                std::cerr << "Interest cannot be satisfied, sending Nack\n";
            }
            m_face.put(lp::Nack(interest));
        }
    }

    void
    Producer::segmentationFile(const Interest &interest)

    {
        const Name &prefix = interest.getName().getPrefix(-1);
        std::cerr << "Segmentation file for prefix: " << prefix.toUri() << "\n";
        std::string prefixstr = prefix.toUri();
        std::string filePathStr;
        if (prefix.size() >= 2)
        {
            // 提取文件名（从第1个组件开始，跳过前缀）
            Name filePath = prefix.getSubName(1);
            filePathStr = filePath.toUri();
            filePathStr = m_fileDir + filePathStr;
            std::cerr << "File path: " << filePathStr << "\n";
        }
        else
        {
            return;
        }

        std::unique_ptr<std::istream> is = std::make_unique<std::ifstream>(filePathStr, std::ios::binary);

        if (!m_options.isQuiet)
        {
            std::cerr << "Loading input ...\n";
        }
        Segmenter segmenter(m_keyChain, m_options.signingInfo);
        // All the data packets are segmented and stored in m_store
        m_store[prefixstr] = segmenter.segment(*is, prefix, m_options.maxSegmentSize, m_options.freshnessPeriod);
        if (!m_options.isQuiet)
        {
            std::cerr << "Published " << m_store[prefixstr].size() << " Data packet" << (m_store[prefixstr].size() > 1 ? "s" : "")
                      << "\n";
        }
    }

} // namespace ndn::chunks